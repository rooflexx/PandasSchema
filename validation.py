import abc
import math
import datetime
import pandas as pd
import numpy as np
import typing

import column
from validation_warning import ValidationWarning
from errors import PanSchArgumentError


class BaseValidation:
    """
    The validation base class that defines any object that can create a list of errors from a Series
    """
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def get_errors(self, series: pd.Series, column: 'column.Column') -> typing.Iterable[ValidationWarning]:
        """
        Return a list of errors in the given series
        :param series:
        :param column:
        :return:
        """


class ElementValidation(BaseValidation):
    """
    Implements the BaseValidation interface by returning a Boolean series for each element that either passes or
    fails the validation
    """
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def get_message(self) -> str:
        """
        Create a message to be displayed whenever this validation fails
        :param value: The value of the failing object (Series, or single value)
        """

    @abc.abstractmethod
    def validate(self, series: pd.Series) -> pd.Series:
        """
        Returns a Boolean series, where each value of False is an element in the Series that has failed the validation
        :param series:
        :return:
        """

    def get_errors(self, series: pd.Series, column: 'column.Column'):

        errors = []

        # Calculate which columns are valid using the child class's validate function, skipping empty entries if the
        # column specifies to do so
        simple_validation = ~self.validate(series)
        if column.allow_empty:
            # Failing results are those that are not empty, and fail the validation
            validated = (series.str.len() > 0) & simple_validation
        else:
            validated = simple_validation

        # Cut down the original series to only ones that failed the validation
        indices = series.index[validated]

        # Use these indices to find the failing items. Also print the index which is probably a row number
        for i in indices:
            element = series[i]
            errors.append(ValidationWarning(
                message=self.get_message(),
                value=element,
                row=i,
                column=series.name
            ))

        return errors


class CustomValidation(ElementValidation):
    """
    Validates using a user-provided function and message.
    """

    def __init__(self, validation: typing.Callable[[pd.Series], pd.Series], message: str):
        """
        :param message: The error message to provide to the user if this validation fails. The row and column and
            failing value will automatically be prepended to this message, so you only have to provide a message that
            describes what went wrong, for example 'failed my validation' will become

            {row: 1, column: "Column Name"}: "Value" failed my validation
        :param validation: A function that takes a pandas Series and returns a boolean Series, where each cell is equal
            to True if the object passed validation, and False if it failed
        """
        self._message = message
        self._validation = validation
        super().__init__()

    def get_message(self):
        return self._message

    def validate(self, series: pd.Series) -> pd.Series:
        return self._validation(series)


class InRangeValidation(ElementValidation):
    """
    Checks that each element in the series is within a given numerical range
    """

    def __init__(self, min: float = -math.inf, max: float = math.inf):
        """
        :param min: The minimum (inclusive) value to accept
        :param max: The maximum (exclusive) value to accept
        """
        self.min = min
        self.max = max

    def get_message(self):
        return 'was not in the range [{}, {})'.format(self.min, self.max)

    def validate(self, series: pd.Series) -> pd.Series:
        series = pd.to_numeric(series)
        return (series >= self.min) & (series < self.max)


class IsDtypeValidation(BaseValidation):
    """
    Checks that a series has a certain numpy dtype
    """

    def __init__(self, dtype: np.dtype):
        """
        :param dtype: The numpy dtype to check the column against
        """
        self.dtype = dtype

    def get_errors(self, series: pd.Series, column: 'column.Column' = None):
        if not np.issubdtype(series.dtype, self.dtype):
            return [ValidationWarning(
                'The column has a dtype of {} which is not a subclass of the required type {}'.format(series.dtype,
                                                                                                      self.dtype))]
        else:
            return []


class CanCallValidation(ElementValidation):
    """
    Validates if a given function can be called on each element in a column without raising an exception
    """

    def __init__(self, func: typing.Callable):
        """
        :param func: A python function that will be called with the value of each cell in the DataFrame. If this
            function throws an error, this cell is considered to have failed the validation. Otherwise it has passed.
        """
        if callable(type):
            self.callable = func
        else:
            raise PanSchArgumentError('The object "{}" passed to CanCallValidation is not callable!'.format(type))
        super().__init__()

    def get_message(self):
        return 'raised an exception when the callable {} was called on it'.format(self.callable)

    def can_call(self, var):
        try:
            self.callable(var)
            return True
        except:
            return False

    def validate(self, series: pd.Series) -> pd.Series:
        return series.apply(self.can_call)


class CanConvertValidation(CanCallValidation):
    """
    Checks if each element in a column can be converted to a Python object type
    """

    """
    Internally this uses the same logic as CanCallValidation since all types are callable in python.
    However this class overrides the error messages to make them more directed towards types
    """

    def __init__(self, _type: type):
        """
        :param _type: Any python type. Its constructor will be called with the value of the individual cell as its
            only argument. If it throws an exception, the value is considered to fail the validation, otherwise it has passed
        """
        if isinstance(_type, type):
            super(CanConvertValidation, self).__init__(_type)
        else:
            raise PanSchArgumentError('{} is not a valid type'.format(_type))

    def get_message(self):
        return 'cannot be converted to type {}'.format(self.callable)


class MatchesRegexValidation(ElementValidation):
    """
    Validates that a regular expression can match somewhere in each element in this column
    """

    def __init__(self, regex: typing.re.Pattern):
        """
        :param regex: A regular expression object, created using re.compile or similar
        """

        self.pattern = regex

    def get_message(self):
        return 'does not match the regex "{}"'.format(self.pattern)

    def validate(self, series: pd.Series) -> pd.Series:
        return series.astype(str).str.contains(self.pattern)


class TrailingWhitespaceValidation(ElementValidation):
    """
    Checks that there is no trailing whitespace in this column
    """

    def __init__(self):
        pass

    def get_message(self):
        return 'contains trailing whitespace'

    def validate(self, series: pd.Series) -> pd.Series:
        return ~series.astype(str).str.contains('\s+$')


class LeadingWhitespaceValidation(ElementValidation):
    """
    Checks that there is no trailing whitespace in this column
    """

    def __init__(self):
        pass

    def get_message(self):
        return 'contains leading whitespace'

    def validate(self, series: pd.Series) -> pd.Series:
        return ~series.astype(str).str.contains('^\s+')


class InListValidation(ElementValidation):
    """
    Checks that each element in this column is contained within a list of possibilities
    """

    def __init__(self, options: typing.Iterable):
        """
        :param options: A list of values to check. If the value of a cell is in this list, it is considered to pass the
            validation
        """
        self.options = options

    def get_message(self):
        return 'is not in the list of legal options ({})'.format(', '.join(self.options))

    def validate(self, series: pd.Series) -> pd.Series:
        return series.isin(self.options)


class DateFormatValidation(ElementValidation):
    """
    Checks that each element in this column is a valid date according to a provided format string
    """

    def __init__(self, date_format: str):
        """
        :param date_format: The date format string to validate the column against. Refer to the date format code
            documentation at https://docs.python.org/3/library/datetime.html#strftime-and-strptime-behavior for a full
            list of format codes
        """
        self.date_format = date_format

    def get_message(self):
        return 'does not match the date format string "{}"'.format(self.date_format)

    def valid_date(self, val):
        try:
            datetime.datetime.strptime(val, self.date_format)
            return True
        except:
            return False

    def validate(self, series: pd.Series) -> pd.Series:
        return series.astype(str).apply(self.valid_date)
import re
from datetime import date
from calendar import monthrange, IllegalMonthError
from django import forms
from django.conf import settings
from django.template.defaultfilters import date as _date
from django.utils.translation import ugettext_lazy as _


CREDIT_CARD_RE = r'^(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|6(?:011|5[0-9][0-9])[0-9]{12}|3[47][0-9]{13}|3(?:0[0-5]|[68][0-9])[0-9]{11}|(?:2131|1800|35\\d{3})\d{11})$'
MONTH_FORMAT = getattr(settings, 'MONTH_FORMAT', 'M')
VERIFICATION_VALUE_RE = r'^([0-9]{3,4})$'


class CreditCardField(forms.CharField):
    """
    Form field that validates credit card numbers.
    """

    default_error_messages = {
        'required': _('Please enter a credit card number.'),
        'invalid': _('The credit card number you entered is invalid.'),
    }

    def __init__(self, *args, **kwargs):
        max_length=kwargs.pop("max_length",19)
        super(CreditCardField,self).__init__(max_length=max_length, *args, **kwargs)

    def clean(self, value):
        def is_luhn_valid(cc):
            num = [int(ii) for ii in cc]
            return not sum(num[::-2] + [sum(divmod(d * 2, 10)) for d in num[-2::-2]]) % 10

        value = value and value.replace(' ', '').replace('-', '')
        if self.required and not value:
            raise form.ValidationError(self.error_messages['required'])
        if value and not (re.match(CREDIT_CARD_RE, value) and is_luhn_valid(value)):
            raise form.ValidationError(self.error_messages['invalid'])
        return value


class ExpiryDateWidget(forms.MultiWidget):
    """
    Widget containing two select boxes for selecting the month and year.
    """

    def decompress(self, value):
        return [value.month, value.year] if value else [None, None]

    def format_output(self, rendered_widgets):
        return '<div class="expirydatefield">%s</div>' % ' '.join(rendered_widgets)


class ExpiryDateField(forms.MultiValueField):
    """
    Form field that validates credit card expiry dates.
    """

    default_error_messages = {
        'invalid_month': _('Please enter a valid month.'),
        'invalid_year': _('Please enter a valid year.'),
        'date_passed': _('This expiry date has passed.'),
    }

    def __init__(self, *args, **kwargs):
        today = date.today()
        error_messages = self.default_error_messages.copy()
        if 'error_messages' in kwargs:
            error_messages.update(kwargs['error_messages'])
        if 'initial' not in kwargs:
            # Set default expiry date based on current month and year
            kwargs['initial'] = today
        months = [(x, '%02d (%s)' % (x, _date(date(2000, x, 1), MONTH_FORMAT))) for x in range(1, 13)]
        years = [(x, x) for x in range(today.year, today.year + 15)]
        fields = (
            forms.ChoiceField(choices=months, error_messages={'invalid': error_messages['invalid_month']}),
            forms.ChoiceField(choices=years, error_messages={'invalid': error_messages['invalid_year']}),
        )
        super(ExpiryDateField, self).__init__(fields, *args, **kwargs)
        self.widget = ExpiryDateWidget(widgets=[fields[0].widget, fields[1].widget])

    def clean(self, value):
        expiry_date = super(ExpiryDateField, self).clean(value)
        if date.today() > expiry_date:
            raise forms.ValidationError(self.error_messages['date_passed'])
        return expiry_date

    def compress(self, data_list):
        if data_list:
            try:
                month = int(data_list[0])
            except (ValueError, TypeError):
                raise forms.ValidationError(self.error_messages['invalid_month'])
            try:
                year = int(data_list[1])
            except (ValueError, TypeError):
                raise forms.ValidationError(self.error_messages['invalid_year'])
            try:
                day = monthrange(year, month)[1] # last day of the month
            except IllegalMonthError:
                raise forms.ValidationError(self.error_messages['invalid_month'])
            except ValueError:
                raise forms.ValidationError(self.error_messages['invalid_year'])
            return date(year, month, day)
        return None


class VerificationValueField(forms.CharField):
    """
    Form field that validates credit card verification values (e.g. CVV2).
    See http://en.wikipedia.org/wiki/Card_Security_Code
    """

    widget = forms.TextInput(attrs={'maxlength': 4})
    default_error_messages = {
        'required': _('Please enter the three- or four-digit verification code for your credit card.'),
        'invalid': _('The verification value you entered is invalid.'),
    }

    def clean(self, value):
        value = value and value.replace(' ', '')
        if not value and self.required:
            raise form.ValidationError(self.error_messages['required'])
        if value and not re.match(VERIFICATION_VALUE_RE, value):
            raise form.ValidationError(self.error_messages['invalid'])
        return value

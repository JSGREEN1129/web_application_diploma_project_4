from decimal import Decimal
from django import forms


class InvestmentPledgeForm(forms.Form):
    amount_gbp = forms.DecimalField(min_value=Decimal("1.00"), max_digits=12, decimal_places=2)

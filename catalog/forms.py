from django import forms
from django.core.exceptions import ValidationError
from nova.core.exceptions import NovaValidationError

from .models import Product


class ProductAdminForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = "__all__"

    def _post_clean(self):
        # Django implements this lifecycle hook; django-stubs omits its private API.
        super()._post_clean()  # pyright: ignore[reportAttributeAccessIssue]
        if self.errors:
            return
        try:
            self.instance._run_validation()
        except NovaValidationError as exc:
            self.add_error(None, ValidationError(str(exc)))

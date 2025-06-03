from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _
from django.contrib.auth.password_validation import UserAttributeSimilarityValidator, MinimumLengthValidator, CommonPasswordValidator, NumericPasswordValidator
from difflib import SequenceMatcher


class CustomUserAttributeSimilarityValidator(UserAttributeSimilarityValidator):
    def __init__(self, user_attributes=None, max_similarity=0.7):
        self.user_attributes = user_attributes or (
            'username', 'first_name', 'last_name', 'email')
        self.max_similarity = max_similarity
        self.min_length = 4
        self.similarity_function = lambda x, y: SequenceMatcher(
            None, x, y).quick_ratio()

    def validate(self, password, user=None):
        if not user:
            return

        for attribute_name in self.user_attributes:
            value = getattr(user, attribute_name, None)
            if not value or not isinstance(value, str):
                continue
            value_parts = value.lower().split()
            for value_part in value_parts:
                if len(value_part) >= self.min_length:
                    if (
                        self.similarity_function(
                            password.lower(),
                            value_part
                        ) > self.max_similarity
                    ):
                        raise ValidationError(
                            "La contraseña es demasiado similar a tu información personal.",
                            code='password_too_similar',
                        )

class CustomMinimumLengthValidator(MinimumLengthValidator):
    def validate(self, password, user=None):
        if len(password) < self.min_length:
            raise ValidationError(
                "La contraseña debe tener al menos %(min_length)d caracteres.",
                code='password_too_short',
                params={'min_length': self.min_length},
            )

class CustomCommonPasswordValidator(CommonPasswordValidator):
    def validate(self, password, user=None):
        if password.lower().strip() in self.passwords:
            raise ValidationError(
                "Esta contraseña es demasiado común.",
                code='password_too_common',
            )

class CustomNumericPasswordValidator(NumericPasswordValidator):
    def validate(self, password, user=None):
        if password.isdigit():
            raise ValidationError(
                "Esta contraseña es completamente numérica.",
                code='password_entirely_numeric',
            )

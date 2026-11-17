from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "email", "username", "first_name", "last_name", "role", "date_joined")
        read_only_fields = ("id", "role", "date_joined")


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    role = serializers.ChoiceField(
        choices=[User.Role.CANDIDATE, User.Role.RECRUITER], default=User.Role.CANDIDATE
    )

    class Meta:
        model = User
        fields = ("id", "email", "username", "first_name", "last_name", "password", "role")

    def validate(self, attrs):
        validate_password(
            attrs["password"], user=User(**{k: v for k, v in attrs.items() if k != "password"})
        )
        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        if user.is_candidate:
            from apps.candidates.models import CandidateProfile

            CandidateProfile.objects.create(user=user)
        return user

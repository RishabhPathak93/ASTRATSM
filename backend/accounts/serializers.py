"""accounts/serializers.py"""
import logging
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import User, RolePermission

logger = logging.getLogger('nexus')


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Extends the default JWT response with the user profile so the frontend
    doesn't need a second round-trip after login.
    """
    def validate(self, attrs):
        data = super().validate(attrs)
        user = self.user

        if not user.is_active:
            raise serializers.ValidationError(
                'Your account has been deactivated. Contact an administrator.'
            )

        data['user'] = {
            'id':          user.id,
            'name':        user.name,
            'email':       user.email,
            'role':        user.role,
            'department':  user.department,
            'initials':    user.initials,
            'permissions': RolePermission.get_for_role(user.role),
        }
        logger.info('Successful login: %s', user.email)
        return data


class UserSerializer(serializers.ModelSerializer):
    initials    = serializers.ReadOnlyField()
    avatar_url  = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()

    class Meta:
        model  = User
        fields = [
            'id', 'name', 'email', 'role', 'department', 'phone',
            'bio', 'is_active', 'date_joined', 'last_seen',
            'initials', 'avatar_url', 'permissions',
        ]
        read_only_fields = ['id', 'date_joined', 'last_seen']

    def get_avatar_url(self, obj):
        request = self.context.get('request')
        if obj.avatar and hasattr(obj.avatar, 'url') and request:
            return request.build_absolute_uri(obj.avatar.url)
        return None

    def get_permissions(self, obj):
        return RolePermission.get_for_role(obj.role)


class UserCreateSerializer(serializers.ModelSerializer):
    password  = serializers.CharField(write_only=True, style={'input_type': 'password'})
    password2 = serializers.CharField(write_only=True, style={'input_type': 'password'}, label='Confirm password')

    class Meta:
        model  = User
        fields = ['name', 'email', 'password', 'password2', 'role', 'department', 'phone']
        extra_kwargs = {
            'email': {'required': True},
            'name':  {'required': True},
            'role':  {'required': True},
        }

    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError('A user with this email already exists.')
        return value

    def validate_name(self, value):
        value = value.strip()
        if len(value) < 2:
            raise serializers.ValidationError('Name must be at least 2 characters.')
        return value

    def validate_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(list(e.messages))
        return value

    def validate(self, attrs):
        if attrs.get('password') != attrs.get('password2'):
            raise serializers.ValidationError({'password2': 'Passwords do not match.'})
        attrs.pop('password2')
        return attrs

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class UserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = User
        fields = ['name', 'department', 'phone', 'bio', 'avatar']

    def validate_name(self, value):
        value = value.strip()
        if len(value) < 2:
            raise serializers.ValidationError('Name must be at least 2 characters.')
        return value

    def validate_avatar(self, value):
        from django.conf import settings
        import os
        if value:
            ext = os.path.splitext(value.name)[1].lower()
            if ext not in settings.ALLOWED_IMAGE_EXTENSIONS:
                raise serializers.ValidationError(
                    f'Unsupported file type. Allowed: {", ".join(settings.ALLOWED_IMAGE_EXTENSIONS)}'
                )
            max_size = settings.MAX_AVATAR_SIZE_MB * 1024 * 1024
            if value.size > max_size:
                raise serializers.ValidationError(
                    f'Avatar must be smaller than {settings.MAX_AVATAR_SIZE_MB} MB.'
                )
        return value


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(required=True, write_only=True)

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError('Current password is incorrect.')
        return value

    def validate_new_password(self, value):
        try:
            validate_password(value, self.context['request'].user)
        except DjangoValidationError as e:
            raise serializers.ValidationError(list(e.messages))
        return value

    def validate(self, attrs):
        if attrs['old_password'] == attrs['new_password']:
            raise serializers.ValidationError(
                {'new_password': 'New password must differ from the current password.'}
            )
        return attrs


class AdminChangeRoleSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=User.Role.choices)


class RolePermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model  = RolePermission
        fields = ['id', 'role', 'permissions', 'updated_by', 'updated_at']
        read_only_fields = ['id', 'updated_by', 'updated_at']

    def validate_permissions(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError('Permissions must be a JSON object.')
        for k, v in value.items():
            if not isinstance(k, str):
                raise serializers.ValidationError('Permission keys must be strings.')
            if not isinstance(v, bool):
                raise serializers.ValidationError(f'Value for "{k}" must be boolean.')
        return value

from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Branch, UserProfile, Product, StockIn, StockOut, Booking, BookingItem, Notification


class BranchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = ['id', 'name', 'location', 'manager_name', 'pickup_days', 'pickup_hours']


class UserProfileSerializer(serializers.ModelSerializer):
    branch_name = serializers.ReadOnlyField(source='branch.name')
    branch_id = serializers.ReadOnlyField(source='branch.id')

    class Meta:
        model = UserProfile
        fields = ['role', 'contact_number', 'location', 'branch', 'branch_name', 'branch_id']


class UserSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer(required=False)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'profile']

    def update(self, instance, validated_data):
        profile_data = validated_data.pop('profile', {})
        instance.first_name = validated_data.get('first_name', instance.first_name)
        instance.save()

        profile = getattr(instance, 'profile', None)
        if profile:
            if 'contact_number' in profile_data:
                profile.contact_number = profile_data['contact_number']
            if 'location' in profile_data:
                profile.location = profile_data['location']
            if 'role' in profile_data:
                profile.role = profile_data['role']
            if 'branch' in profile_data:
                profile.branch = profile_data['branch']
            profile.save()

        return instance


class ProductSerializer(serializers.ModelSerializer):
    added_by_name = serializers.ReadOnlyField(source='added_by.username')

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'size', 'color',
            'quantity', 'buying_price', 'selling_price', 'active',
            'image', 'added_by', 'added_by_name', 'created_at'
        ]
        read_only_fields = ['added_by', 'added_by_name', 'created_at']


class StockInSerializer(serializers.ModelSerializer):
    product_name = serializers.ReadOnlyField(source='product.name')
    product_size = serializers.ReadOnlyField(source='product.size')
    product_color = serializers.ReadOnlyField(source='product.color')
    user_name = serializers.ReadOnlyField(source='user.username')

    class Meta:
        model = StockIn
        fields = ['id', 'product', 'product_name', 'product_size', 'product_color', 'user', 'user_name', 'quantity', 'buying_price', 'created_at']


class StockOutSerializer(serializers.ModelSerializer):
    product_name = serializers.ReadOnlyField(source='product.name')
    product_size = serializers.ReadOnlyField(source='product.size')
    product_color = serializers.ReadOnlyField(source='product.color')
    branch_name = serializers.SerializerMethodField()
    branch_id = serializers.ReadOnlyField(source='branch.id')
    user_name = serializers.ReadOnlyField(source='user.username')

    class Meta:
        model = StockOut
        fields = [
            'id', 'product', 'product_name', 'product_size', 'product_color',
            'branch', 'branch_id', 'branch_name', 'user', 'user_name', 'quantity', 'selling_price',
            'customer_name', 'customer_phone', 'created_at'
        ]

    def get_branch_name(self, obj):
        return obj.branch.name if obj.branch else 'Main Branch'


class BookingItemSerializer(serializers.ModelSerializer):
    product_name = serializers.ReadOnlyField(source='product.name')
    product_size = serializers.ReadOnlyField(source='product.size')
    product_color = serializers.ReadOnlyField(source='product.color')
    product_branch = serializers.ReadOnlyField(source='product.branch.name')

    class Meta:
        model = BookingItem
        fields = [
            'id', 'product', 'product_name', 'product_size', 'product_color',
            'product_branch', 'quantity', 'selling_price'
        ]


class BookingSerializer(serializers.ModelSerializer):
    items = BookingItemSerializer(many=True, read_only=True)
    customer_username = serializers.ReadOnlyField(source='customer.username')
    customer_email = serializers.ReadOnlyField(source='customer.email')
    branch_name = serializers.ReadOnlyField(source='branch.name')
    fulfilled_by_name = serializers.ReadOnlyField(source='fulfilled_by.username')
    total_amount = serializers.SerializerMethodField()

    class Meta:
        model = Booking
        fields = [
            'id', 'booking_ref', 'customer', 'customer_username', 'customer_email',
            'customer_name', 'customer_phone', 'branch', 'branch_name', 'status',
            'delivery_method', 'delivery_fee', 'delivery_address', 'buddy_group',
            'fulfilled_by', 'fulfilled_by_name', 'fulfilled_at',
            'items', 'total_amount', 'created_at', 'updated_at'
        ]

    def get_total_amount(self, obj):
        items_total = sum(
            float(item.selling_price) * item.quantity
            for item in obj.items.all()
        )
        return items_total + float(obj.delivery_fee or 0)


class NotificationSerializer(serializers.ModelSerializer):
    user_name = serializers.ReadOnlyField(source='user.username')
    branch_name = serializers.ReadOnlyField(source='branch.name')

    class Meta:
        model = Notification
        fields = [
            'id', 'user', 'user_name', 'branch', 'branch_name',
            'title', 'message', 'notification_type', 'is_read', 'created_at'
        ]

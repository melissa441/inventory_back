from django.contrib import admin
from .models import Branch, UserProfile, Product, StockIn, StockOut


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ('name', 'location', 'manager_name')
    search_fields = ('name', 'location', 'manager_name')


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'branch', 'contact_number', 'location')
    list_filter = ('role', 'branch')
    search_fields = ('user__username', 'user__email', 'contact_number')


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'size',
        'color',
        'quantity',
        'buying_price',
        'selling_price',
        'active',
        'added_by',
        'created_at'
    )
    list_filter = ('size', 'color', 'active')
    search_fields = ('name', 'color')
    list_editable = ('quantity', 'selling_price', 'active')
    ordering = ('-created_at',)


@admin.register(StockIn)
class StockInAdmin(admin.ModelAdmin):
    list_display = (
        'product',
        'user',
        'quantity',
        'buying_price',
        'created_at'
    )
    list_filter = ('created_at',)
    search_fields = ('product__name', 'user__username')
    ordering = ('-created_at',)


@admin.register(StockOut)
class StockOutAdmin(admin.ModelAdmin):
    list_display = (
        'product',
        'branch',
        'user',
        'quantity',
        'selling_price',
        'customer_name',
        'customer_phone',
        'created_at'
    )
    list_filter = ('branch', 'created_at')
    search_fields = (
        'product__name',
        'user__username',
        'customer_name',
        'customer_phone'
    )
    ordering = ('-created_at',)

from django.db import models
from django.contrib.auth.models import User
import uuid


class Branch(models.Model):
    name = models.CharField(max_length=100, unique=True)
    location = models.CharField(max_length=200)
    manager_name = models.CharField(max_length=100, default='Unassigned')
    pickup_days = models.CharField(max_length=100, blank=True, null=True)
    pickup_hours = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return self.name


class UserProfile(models.Model):
    ROLE_CHOICES = (
        ('super-admin', 'Super Admin'),
        ('branch-manager', 'Branch Manager'),
        ('sales-agent', 'Sales Agent'),
        ('customer', 'Customer'),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='sales-agent')
    contact_number = models.CharField(max_length=20, blank=True, null=True)
    location = models.CharField(max_length=200, blank=True, null=True)
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, blank=True, null=True, related_name='staff')

    def save(self, *args, **kwargs):
        old_branch = None
        old_role = None
        if self.pk:
            try:
                old_profile = UserProfile.objects.get(pk=self.pk)
                old_branch = old_profile.branch
                old_role = old_profile.role
            except UserProfile.DoesNotExist:
                pass

        super().save(*args, **kwargs)

        # Auto-sync branch manager_name
        if self.role == 'branch-manager' and self.branch:
            self.branch.manager_name = self.user.first_name or self.user.username
            self.branch.save()
            if old_branch and old_branch != self.branch:
                if not UserProfile.objects.filter(branch=old_branch, role='branch-manager').exists():
                    old_branch.manager_name = 'Unassigned'
                    old_branch.save()
        else:
            if old_branch:
                if not UserProfile.objects.filter(branch=old_branch, role='branch-manager').exists():
                    old_branch.manager_name = 'Unassigned'
                    old_branch.save()
            if self.branch and (old_role == 'branch-manager' or old_branch == self.branch):
                if not UserProfile.objects.filter(branch=self.branch, role='branch-manager').exclude(pk=self.pk).exists():
                    self.branch.manager_name = 'Unassigned'
                    self.branch.save()

    def __str__(self):
        return f"{self.user.username} - {self.role}"


class Product(models.Model):
    SIZE_CHOICES = (
        ('S', 'S'),
        ('M', 'M'),
        ('L', 'L'),
        ('XL', 'XL'),
    )
    name = models.CharField(max_length=150)
    size = models.CharField(max_length=10, choices=SIZE_CHOICES, default='M')
    color = models.CharField(max_length=50)
    quantity = models.PositiveIntegerField(default=0)
    buying_price = models.DecimalField(max_digits=12, decimal_places=2)
    selling_price = models.DecimalField(max_digits=12, decimal_places=2)
    active = models.BooleanField(default=True)
    image = models.TextField(blank=True, null=True)
    added_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('name', 'size', 'color')

    def __str__(self):
        return f"{self.name} ({self.color} - {self.size})"


class StockIn(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='stock_ins')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    quantity = models.PositiveIntegerField()
    buying_price = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"StockIn: {self.quantity}x {self.product.name} at {self.created_at}"


class StockOut(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='stock_outs')
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, blank=True, related_name='sales')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    quantity = models.PositiveIntegerField()
    selling_price = models.DecimalField(max_digits=12, decimal_places=2)
    customer_name = models.CharField(max_length=100, blank=True, null=True)
    customer_phone = models.CharField(max_length=30, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"StockOut (Sale): {self.quantity}x {self.product.name} at {self.created_at}"


class Booking(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('fulfilled', 'Fulfilled'),
        ('cancelled', 'Cancelled'),
    )
    booking_ref = models.CharField(max_length=20, unique=True, blank=True)
    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bookings')
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, related_name='bookings')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    customer_name = models.CharField(max_length=100, blank=True)
    customer_phone = models.CharField(max_length=30, blank=True)
    delivery_method = models.CharField(max_length=50, default='Pick Up')
    delivery_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    delivery_address = models.TextField(blank=True, null=True)
    buddy_group = models.CharField(max_length=100, blank=True, null=True)
    fulfilled_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='fulfilled_bookings')
    fulfilled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.booking_ref:
            import random
            self.booking_ref = f"RES-{random.randint(10000, 99999)}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Booking {self.booking_ref} by {self.customer.username} - {self.status}"


class BookingItem(models.Model):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='booking_items')
    quantity = models.PositiveIntegerField()
    selling_price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.quantity}x {self.product.name} (Booking {self.booking.booking_ref})"


class Notification(models.Model):
    NOTIFICATION_TYPES = (
        ('reservation', 'Customer Reservation'),
        ('stock', 'Low Stock Alert'),
        ('sale', 'Sale Handover Completed'),
        ('system', 'System Alert'),
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications', null=True, blank=True)
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, null=True, blank=True, related_name='notifications')
    title = models.CharField(max_length=150)
    message = models.TextField()
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES, default='system')
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.notification_type}] {self.title} (Read: {self.is_read})"


# ──────────────────────────────────────────────────────────────
# Signals
# ──────────────────────────────────────────────────────────────
from django.db.models.signals import pre_delete
from django.dispatch import receiver


@receiver(pre_delete, sender=UserProfile)
def clear_branch_manager_on_profile_delete(sender, instance, **kwargs):
    """
    When a UserProfile is deleted (e.g., because its User was deleted),
    if that user was a branch-manager and no other branch-manager exists
    for the same branch, set the branch's manager_name back to 'Unassigned'.
    """
    if instance.role == 'branch-manager' and instance.branch:
        branch = instance.branch
        # Check if any OTHER branch-manager is still assigned to this branch
        remaining = UserProfile.objects.filter(
            branch=branch,
            role='branch-manager'
        ).exclude(pk=instance.pk).exists()

        if not remaining:
            branch.manager_name = 'Unassigned'
            branch.save()

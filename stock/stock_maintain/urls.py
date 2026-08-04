from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    BranchViewSet, ProductViewSet, StockInViewSet,
    SalesCheckoutViewSet, LoginView, SignupView,
    DashboardStatsView, UserViewSet, BookingViewSet, NotificationViewSet
)

router = DefaultRouter()
router.register('branches', BranchViewSet, basename='branch')
router.register('products', ProductViewSet, basename='product')
router.register('stock-in', StockInViewSet, basename='stockin')
router.register('sales', SalesCheckoutViewSet, basename='sale')
router.register('users', UserViewSet, basename='user')
router.register('bookings', BookingViewSet, basename='booking')
router.register('notifications', NotificationViewSet, basename='notification')

urlpatterns = [
    # Auth routing
    path('auth/login/', LoginView.as_view(), name='login'),
    path('auth/signup/', SignupView.as_view(), name='signup'),

    # Custom dashboard aggregated KPIs stats endpoint (supports ?branch_id=X)
    path('dashboard/stats/', DashboardStatsView.as_view(), name='dashboard-stats'),

    # ViewSet CRUD actions
    path('', include(router.urls)),
]

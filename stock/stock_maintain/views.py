from rest_framework import viewsets, status, views
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.authentication import TokenAuthentication
from rest_framework.authtoken.models import Token
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.db.models import Sum, F, Q
from django.utils import timezone
from datetime import datetime, timedelta

from .models import Branch, UserProfile, Product, StockIn, StockOut, Booking, BookingItem, Notification
from .serializers import (
    BranchSerializer, UserSerializer, ProductSerializer,
    StockInSerializer, StockOutSerializer, BookingSerializer, NotificationSerializer
)


class LoginView(views.APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email')
        password = request.data.get('password')

        if not email or not password:
            return Response(
                {"error": "Please provide both email and password."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {"error": "Invalid credentials. User with this email does not exist."},
                status=status.HTTP_401_UNAUTHORIZED
            )

        user = authenticate(username=user.username, password=password)
        if user is not None:
            token, _ = Token.objects.get_or_create(user=user)
            return Response({
                "token": token.key,
                "user": UserSerializer(user).data
            })
        else:
            return Response(
                {"error": "Invalid email or password."},
                status=status.HTTP_401_UNAUTHORIZED
            )


class SignupView(views.APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        name = request.data.get('name')
        email = request.data.get('email')
        phone = request.data.get('phone', '')
        branch_id = request.data.get('branch_id')
        branch_name = request.data.get('branch', 'Main Branch')
        location = request.data.get('location', '')
        password = request.data.get('password')
        role = request.data.get('role', 'sales-agent')

        if not name or not email or not password:
            return Response(
                {"error": "Name, email, and password are required fields."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if User.objects.filter(email=email).exists():
            return Response(
                {"error": "User with this email already exists."},
                status=status.HTTP_400_BAD_REQUEST
            )

        username = email.split('@')[0]
        suffix = 1
        while User.objects.filter(username=username).exists():
            username = f"{email.split('@')[0]}{suffix}"
            suffix += 1

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=name
        )

        # Resolve branch: by ID first (preferred), then by name (if valid)
        branch = None
        if branch_id:
            try:
                branch = Branch.objects.get(id=branch_id)
            except Branch.DoesNotExist:
                pass
        if not branch and branch_name and branch_name not in ['', 'Unassigned', 'none', 'None']:
            branch, _ = Branch.objects.get_or_create(
                name=branch_name,
                defaults={'location': location or 'HQ Office'}
            )

        UserProfile.objects.create(
            user=user,
            role=role,
            contact_number=phone,
            location=location,
            branch=branch
        )

        token = Token.objects.create(user=user)
        return Response({
            "token": token.key,
            "user": UserSerializer(user).data
        }, status=status.HTTP_201_CREATED)


class BranchViewSet(viewsets.ModelViewSet):
    queryset = Branch.objects.all()
    serializer_class = BranchSerializer
    permission_classes = [AllowAny]


class ProductViewSet(viewsets.ModelViewSet):
    serializer_class = ProductSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        qs = Product.objects.all().order_by('-created_at')
        active_only = self.request.query_params.get('active_only')
        if active_only == 'true':
            qs = qs.filter(active=True)
        return qs

    def perform_create(self, serializer):
        user = self.request.user if self.request.user.is_authenticated else None
        serializer.save(added_by=user)

    @action(detail=True, methods=['post'])
    def restock(self, request, pk=None):
        product = self.get_object()
        qty = int(request.data.get('quantity', 50))

        product.quantity += qty
        product.save()

        user = request.user if request.user.is_authenticated else None
        StockIn.objects.create(
            product=product,
            user=user,
            quantity=qty,
            buying_price=product.buying_price
        )

        return Response(ProductSerializer(product).data)

    @action(detail=True, methods=['post'])
    def toggle_active(self, request, pk=None):
        """Branch manager action: toggle active/inactive without deleting."""
        product = self.get_object()
        product.active = not product.active
        product.save()
        state = "activated" if product.active else "deactivated"
        return Response({
            "message": f"Product {state} successfully.",
            "product": ProductSerializer(product).data
        })


class StockInViewSet(viewsets.ModelViewSet):
    queryset = StockIn.objects.all().order_by('-created_at')
    serializer_class = StockInSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        product_id = request.data.get('product')
        qty = int(request.data.get('quantity', 0))
        price = float(request.data.get('buying_price', 0))

        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return Response({"error": "Product not found."}, status=status.HTTP_404_NOT_FOUND)

        product.quantity += qty
        product.save()

        user = request.user if request.user.is_authenticated else None
        stock_in = StockIn.objects.create(
            product=product,
            user=user,
            quantity=qty,
            buying_price=price
        )

        serializer = self.get_serializer(stock_in)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class SalesCheckoutViewSet(viewsets.ModelViewSet):
    serializer_class = StockOutSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        qs = StockOut.objects.all().order_by('-created_at')
        branch_id = self.request.query_params.get('branch_id')
        if branch_id:
            qs = qs.filter(branch_id=branch_id)
        return qs

    def create(self, request, *args, **kwargs):
        product_id = request.data.get('product')
        qty = int(request.data.get('quantity', 0))
        price = float(request.data.get('selling_price', 0))
        customer_name = request.data.get('customer_name', '')
        customer_phone = request.data.get('customer_phone', '')

        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return Response({"error": "Product not found."}, status=status.HTTP_404_NOT_FOUND)

        # Calculate pending booked items to prevent selling booked stock
        pending_booked = BookingItem.objects.filter(
            product=product,
            booking__status='pending'
        ).aggregate(total=Sum('quantity'))['total'] or 0
        available_stock = product.quantity - pending_booked

        if available_stock < qty:
            return Response(
                {"error": f"Cannot checkout: requested quantity {qty} exceeds available unbooked stock ({available_stock} available, {pending_booked} booked)."},
                status=status.HTTP_400_BAD_REQUEST
            )


        old_quantity = product.quantity
        product.quantity -= qty
        product.save()

        user = request.user if request.user.is_authenticated else None
        branch_id = request.data.get('branch_id') or request.data.get('branch')
        branch = None
        if branch_id:
            try:
                branch = Branch.objects.get(id=branch_id)
            except Branch.DoesNotExist:
                pass
        if not branch and user and hasattr(user, 'profile') and user.profile.branch:
            branch = user.profile.branch

        # Log low stock notification if crossing below 10
        if old_quantity >= 10 and product.quantity < 10:
            Notification.objects.create(
                branch=branch,
                notification_type='stock',
                title=f"Low Stock Alert: {product.name}",
                message=f"Product '{product.name}' ({product.size}/{product.color}) down to {product.quantity} items."
            )

        sale = StockOut.objects.create(
            product=product,
            branch=branch,
            user=user,
            quantity=qty,
            selling_price=price,
            customer_name=customer_name,
            customer_phone=customer_phone
        )

        serializer = self.get_serializer(sale)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class BookingViewSet(viewsets.ModelViewSet):
    serializer_class = BookingSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        qs = Booking.objects.all().prefetch_related('items__product').order_by('-created_at')
        branch_id = self.request.query_params.get('branch_id')
        customer_id = self.request.query_params.get('customer_id')
        booking_status = self.request.query_params.get('status')

        if branch_id:
            qs = qs.filter(branch_id=branch_id)
        if customer_id:
            qs = qs.filter(customer_id=customer_id)
        if booking_status:
            qs = qs.filter(status=booking_status)
        return qs

    def create(self, request, *args, **kwargs):
        """
        Create a booking with items. Locks stock immediately.
        Expected payload:
        {
          "customer_id": 5,
          "branch_id": 2,
          "customer_name": "...",
          "customer_phone": "...",
          "items": [
            {"product_id": 10, "quantity": 2, "selling_price": 25.00},
            ...
          ]
        }
        """
        customer_id = request.data.get('customer_id')
        branch_id = request.data.get('branch_id')
        customer_name = request.data.get('customer_name', '')
        customer_phone = request.data.get('customer_phone', '')
        items_data = request.data.get('items', [])

        if not customer_id or not branch_id or not items_data:
            return Response(
                {"error": "customer_id, branch_id, and items are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            customer = User.objects.get(id=customer_id)
        except User.DoesNotExist:
            return Response({"error": "Customer not found."}, status=status.HTTP_404_NOT_FOUND)

        try:
            branch = Branch.objects.get(id=branch_id)
        except Branch.DoesNotExist:
            return Response({"error": "Branch not found."}, status=status.HTTP_404_NOT_FOUND)

        # Validate all items have stock before committing
        resolved_items = []
        for item_data in items_data:
            product_id = item_data.get('product_id')
            qty = int(item_data.get('quantity', 1))
            try:
                product = Product.objects.get(id=product_id)
            except Product.DoesNotExist:
                return Response(
                    {"error": f"Product ID {product_id} not found."},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Check stock accounting for existing pending bookings
            pending_booked = BookingItem.objects.filter(
                product=product,
                booking__status='pending'
            ).aggregate(total=Sum('quantity'))['total'] or 0
            available = product.quantity - pending_booked

            if available < qty:
                return Response(
                    {"error": f"Insufficient stock for \"{product.name}\" ({product.size}/{product.color}). Available: {available}, Requested: {qty}."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            resolved_items.append({
                'product': product,
                'quantity': qty,
                'selling_price': float(item_data.get('selling_price', product.selling_price))
            })

        delivery_method = request.data.get('delivery_method', 'Pick Up')
        delivery_fee = float(request.data.get('delivery_fee', 0))
        delivery_address = request.data.get('delivery_address', '')
        buddy_group = request.data.get('buddy_group', '')

        # All items valid — create booking
        booking = Booking.objects.create(
            customer=customer,
            branch=branch,
            status='pending',
            customer_name=customer_name or customer.first_name,
            customer_phone=customer_phone,
            delivery_method=delivery_method,
            delivery_fee=delivery_fee,
            delivery_address=delivery_address,
            buddy_group=buddy_group
        )

        for item in resolved_items:
            BookingItem.objects.create(
                booking=booking,
                product=item['product'],
                quantity=item['quantity'],
                selling_price=item['selling_price']
            )

        # Automatically log notification in database for branch staff
        Notification.objects.create(
            branch=branch,
            user=customer,
            notification_type='reservation',
            title=f"New Reservation #{booking.booking_ref}",
            message=f"Customer {booking.customer_name} reserved items at {branch.name}. Stock locked awaiting pickup."
        )

        return Response(BookingSerializer(booking).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def fulfill(self, request, pk=None):
        """Agent/Manager: Mark booking as fulfilled, deduct stock, clear customer cart."""
        booking = self.get_object()

        if booking.status != 'pending':
            return Response(
                {"error": f"Booking is already {booking.status}. Only pending bookings can be fulfilled."},
                status=status.HTTP_400_BAD_REQUEST
            )

        agent = request.user if request.user.is_authenticated else None

        for item in booking.items.all():
            product = item.product
            if product.quantity < item.quantity:
                return Response(
                    {"error": f"Stock insufficient for {product.name}. Cannot fulfill."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            # Deduct actual stock
            old_quantity = product.quantity
            product.quantity -= item.quantity
            product.save()

            # Log low stock notification if crossing below 10
            if old_quantity >= 10 and product.quantity < 10:
                Notification.objects.create(
                    branch=product.branch,
                    notification_type='stock',
                    title=f"Low Stock Alert: {product.name}",
                    message=f"Product '{product.name}' ({product.size}/{product.color}) at {product.branch.name} down to {product.quantity} items."
                )

            # Log sale transaction
            StockOut.objects.create(
                product=product,
                branch=booking.branch,
                user=agent,
                quantity=item.quantity,
                selling_price=item.selling_price,
                customer_name=booking.customer_name,
                customer_phone=booking.customer_phone
            )

        booking.status = 'fulfilled'
        booking.fulfilled_by = agent
        booking.fulfilled_at = timezone.now()
        booking.save()

        # Log completion notification in database
        Notification.objects.create(
            branch=booking.branch,
            user=booking.customer,
            notification_type='sale',
            title=f"Order #{booking.booking_ref} Handover Completed",
            message=f"Reservation #{booking.booking_ref} fulfilled by staff at {booking.branch.name}."
        )

        return Response({
            "message": f"Booking {booking.booking_ref} fulfilled successfully.",
            "booking": BookingSerializer(booking).data
        })

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Customer or Manager: Cancel a pending booking, releasing locked stock."""
        booking = self.get_object()

        if booking.status != 'pending':
            return Response(
                {"error": f"Cannot cancel a booking that is already {booking.status}."},
                status=status.HTTP_400_BAD_REQUEST
            )

        booking.status = 'cancelled'
        booking.save()

        return Response({
            "message": f"Booking {booking.booking_ref} cancelled. Stock units released.",
            "booking": BookingSerializer(booking).data
        })


class DashboardStatsView(views.APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        branch_id = request.query_params.get('branch_id')

        # Base querysets — products central, sales scoped by branch if provided
        products_qs = Product.objects.all()
        if branch_id:
            sales_qs = StockOut.objects.filter(branch_id=branch_id)
        else:
            sales_qs = StockOut.objects.all()

        total_products = products_qs.count()
        total_stock = products_qs.aggregate(sum=Sum('quantity'))['sum'] or 0

        sales_data = sales_qs.annotate(line_total=F('quantity') * F('selling_price')).aggregate(sum=Sum('line_total'))
        total_sales_revenue = sales_data['sum'] or 0.0

        total_branches = Branch.objects.count()
        total_users = User.objects.count()

        # Low stock alerts
        low_stock_products = products_qs.filter(quantity__lt=10).order_by('quantity')
        low_stock_serialized = ProductSerializer(low_stock_products, many=True).data

        # Recent transactions
        recent_sales = sales_qs.order_by('-created_at')[:8]
        recent_sales_serialized = StockOutSerializer(recent_sales, many=True).data

        # Branch performance (calculated from actual StockOut transaction locations)
        branch_stats = []
        for branch in Branch.objects.all():
            b_sales = StockOut.objects.filter(branch=branch).annotate(
                line_total=F('quantity') * F('selling_price')
            ).aggregate(sum=Sum('line_total'))['sum'] or 0.0
            branch_stats.append({
                "id": branch.id,
                "name": branch.name,
                "sales": float(b_sales)
            })

        # Monthly Sales trend (last 6 calendar months)
        labels = []
        sales_amounts = []

        now = timezone.now()
        cur_year = now.year
        cur_month = now.month

        for i in range(5, -1, -1):
            target_month = cur_month - i
            target_year = cur_year
            while target_month <= 0:
                target_month += 12
                target_year -= 1

            month_start = timezone.datetime(target_year, target_month, 1, 0, 0, 0, tzinfo=now.tzinfo)
            if target_month == 12:
                month_end = timezone.datetime(target_year + 1, 1, 1, 0, 0, 0, tzinfo=now.tzinfo)
            else:
                month_end = timezone.datetime(target_year, target_month + 1, 1, 0, 0, 0, tzinfo=now.tzinfo)

            monthly_revenue = sales_qs.filter(
                created_at__gte=month_start,
                created_at__lt=month_end
            ).annotate(
                line_total=F('quantity') * F('selling_price')
            ).aggregate(sum=Sum('line_total'))['sum'] or 0.0

            labels.append(month_start.strftime('%b'))
            sales_amounts.append(float(monthly_revenue))

        return Response({
            "kpis": {
                "total_products": total_products,
                "total_stock": total_stock,
                "total_sales": float(total_sales_revenue),
                "total_branches": total_branches,
                "total_users": total_users
            },
            "low_stock_alerts": low_stock_serialized,
            "recent_transactions": recent_sales_serialized,
            "branch_performance": branch_stats,
            "monthly_sales_chart": {
                "labels": labels,
                "data": sales_amounts
            }
        })


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all().order_by('id')
    serializer_class = UserSerializer
    permission_classes = [AllowAny]


class NotificationViewSet(viewsets.ModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        qs = Notification.objects.all().order_by('-created_at')
        branch_id = self.request.query_params.get('branch_id')
        user_id = self.request.query_params.get('user_id')

        if branch_id:
            qs = qs.filter(branch_id=branch_id)
        if user_id:
            qs = qs.filter(user_id=user_id)
        return qs

    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        n = self.get_object()
        n.is_read = True
        n.save()
        return Response({"message": "Marked as read."})

    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        branch_id = request.data.get('branch_id')
        user_id = request.data.get('user_id')
        qs = Notification.objects.filter(is_read=False)
        if branch_id:
            qs = qs.filter(branch_id=branch_id)
        if user_id:
            qs = qs.filter(user_id=user_id)
        qs.update(is_read=True)
        return Response({"message": "All notifications marked as read."})

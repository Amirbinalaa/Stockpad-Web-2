from django.core.management.base import BaseCommand
from api.models import User, Material, Category
import decimal


class Command(BaseCommand):
    help = 'Seeds the database with demo users, categories and materials'

    def handle(self, *args, **kwargs):
        self.stdout.write('🌱 Seeding StockPad database...')

        # ── Demo Users ────────────────────────────────────────────────────────
        demo_users = [
            {'username': 'engineer1', 'email': 'engineer@demo.com', 'role': 'engineer'},
            {'username': 'warehouse1', 'email': 'warehouse@demo.com', 'role': 'warehouse'},
            {'username': 'manager1',  'email': 'manager@demo.com',  'role': 'manager'},
        ]
        for u in demo_users:
            if not User.objects.filter(username=u['username']).exists():
                new_user = User.objects.create_user(
                    username=u['username'],
                    email=u['email'],
                    password='demo1234',
                )
                # Role is stored on the Profile (OneToOne with User)
                try:
                    new_user.profile.role = u['role']
                    new_user.profile.save()
                except Exception:
                    pass  # Profile may auto-create via signal or not exist yet
                self.stdout.write(f"  ✅ Created user: {u['username']} / demo1234 ({u['role']})")
            else:
                self.stdout.write(f"  ⏭  User exists: {u['username']}")

        # ── Categories ────────────────────────────────────────────────────────
        category_names = [
            'Building Materials', 'Steel & Metal', 'Paints & Coatings',
            'Finishing', 'Plumbing', 'Electrical', 'Safety & PPE',
        ]
        cats = {}
        for name in category_names:
            cat, created = Category.objects.get_or_create(name=name)
            cats[name] = cat
            status_str = '✅ Created' if created else '⏭  Exists '
            self.stdout.write(f"  {status_str} category: {name}")

        # ── Materials ─────────────────────────────────────────────────────────
        materials_data = [
            # name, category, qty, min_qty, unit, unit_cost, status
            ('Portland Cement',        'Building Materials', 150,  30, 'Bags',    '12.50',  'In Stock'),
            ('Steel Rebar 12mm',       'Steel & Metal',       45,  50, 'Tons',    '850.00', 'Low Stock'),
            ('Fine Construction Sand', 'Building Materials', 200,  40, 'Tons',     '25.00', 'In Stock'),
            ('Premium White Paint',    'Paints & Coatings',    0,  10, 'Gallons',  '35.00', 'Out of Stock'),
            ('PVC Pipes 4"',           'Plumbing',           500,  80, 'Units',     '8.75', 'In Stock'),
            ('Ceramic Tiles',          'Finishing',          320,  60, 'sqm',      '22.00', 'In Stock'),
            ('Electrical Wire 2.5mm',  'Electrical',         120,  25, 'Rolls',    '15.00', 'In Stock'),
            ('Copper Pipe 15mm',       'Plumbing',            80,  20, 'Meters',   '18.50', 'In Stock'),
            ('Red Brick',              'Building Materials', 5000, 500,'Pieces',    '0.45', 'In Stock'),
            ('Glass Sheets 6mm',       'Building Materials',   15,  20, 'Sheets',  '55.00', 'Low Stock'),
            ('Safety Helmets',         'Safety & PPE',        40,  15, 'Units',    '12.00', 'In Stock'),
            ('Sandstone Floor Tiles',  'Finishing',            25,  30, 'sqm',     '45.00', 'Low Stock'),
            ('Circuit Breaker 40A',    'Electrical',           35,  10, 'Units',   '28.00', 'In Stock'),
            ('HDPE Water Pipe 50mm',   'Plumbing',            200,  40, 'Meters',  '14.00', 'In Stock'),
            ('Exterior Primer',        'Paints & Coatings',    18,  10, 'Gallons', '22.00', 'In Stock'),
        ]

        for name, cat_name, qty, min_qty, unit, cost, sts in materials_data:
            cat = cats.get(cat_name)
            mat, created = Material.objects.get_or_create(
                name=name,
                defaults={
                    'category': cat,
                    'quantity_available': qty,
                    'min_stock_level': min_qty,
                    'unit': unit,
                    'unit_cost': decimal.Decimal(cost),
                    'status': sts,
                }
            )
            status_str = '✅ Created' if created else '⏭  Exists '
            self.stdout.write(f"  {status_str} material: {name}")

        self.stdout.write(self.style.SUCCESS('\n✅ Database seeded successfully!'))
        self.stdout.write(self.style.SUCCESS('   Login: engineer1 / demo1234  (engineer)'))
        self.stdout.write(self.style.SUCCESS('   Login: warehouse1 / demo1234  (warehouse)'))
        self.stdout.write(self.style.SUCCESS('   Login: manager1   / demo1234  (manager)'))
        self.stdout.write(self.style.SUCCESS('   Login: admin      / admin123  (superuser)'))

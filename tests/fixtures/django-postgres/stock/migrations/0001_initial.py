from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name="Item",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("sku", models.CharField(max_length=20, unique=True)),
                ("quantity", models.PositiveIntegerField(default=0)),
                ("attributes", models.JSONField(default=dict)),
            ],
        ),
    ]

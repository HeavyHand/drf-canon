from django.db import models


class Item(models.Model):
    name = models.CharField(max_length=50)
    price = models.DecimalField(max_digits=8, decimal_places=2, default=0)

    def __str__(self) -> str:
        return self.name

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from unittest.mock import patch

from listings.models import Listing

User = get_user_model()


class EstimateReturnTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="owner", email="owner@example.com", password="Password123!"
        )
        self.investor = User.objects.create_user(
            username="investor", email="investor@example.com", password="Password123!"
        )

        self.listing = Listing.objects.create(
            owner=self.owner,
            status=Listing.Status.ACTIVE,
            return_band=Listing.ReturnBand.R5_9,
            return_type=Listing.ReturnType.PAYBACK,
            duration_days=10,
        )

    def test_estimate_requires_login(self):
        url = reverse("listings:estimate_return", args=[self.listing.pk])
        resp = self.client.get(url, {"amount": "100"})
        self.assertEqual(resp.status_code, 302)

    def test_estimate_invalid_amount(self):
        self.client.force_login(self.investor)
        url = reverse("listings:estimate_return", args=[self.listing.pk])
        resp = self.client.get(url, {"amount": "not-a-number"})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["ok"], False)

    def test_estimate_amount_must_be_positive(self):
        self.client.force_login(self.investor)
        url = reverse("listings:estimate_return", args=[self.listing.pk])
        resp = self.client.get(url, {"amount": "0"})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["ok"], False)

    @patch("listings.views.get_return_pct_range", return_value=(Decimal("5"), Decimal("9")))
    def test_estimate_success(self, mock_range):
        self.client.force_login(self.investor)
        url = reverse("listings:estimate_return", args=[self.listing.pk])
        resp = self.client.get(url, {"amount": "100"})
        self.assertEqual(resp.status_code, 200)

        data = resp.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["min_pct"], "5")
        self.assertEqual(data["max_pct"], "9")
        self.assertEqual(data["profit_min"], "5.00")
        self.assertEqual(data["profit_max"], "9.00")
        self.assertEqual(data["total_min"], "105.00")
        self.assertEqual(data["total_max"], "109.00")
        self.assertEqual(data["duration_days"], 10)

    @patch("listings.views.get_return_pct_range", side_effect=Exception("bad band"))
    def test_estimate_bad_return_band(self, mock_range):
        self.client.force_login(self.investor)
        url = reverse("listings:estimate_return", args=[self.listing.pk])
        resp = self.client.get(url, {"amount": "100"})
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.json()["ok"])

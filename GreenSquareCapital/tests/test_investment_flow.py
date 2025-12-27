from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from unittest.mock import patch

from investments.models import Investment
from listings.models import Listing

User = get_user_model()


class InvestmentFlowClientTests(TestCase):
    def setUp(self):
        self.investor = User.objects.create_user(
            username="investor1",
            email="investor1@example.com",
            password="Password123!",
        )
        self.owner = User.objects.create_user(
            username="owner1",
            email="owner1@example.com",
            password="Password123!",
        )

        now = timezone.now()
        self.listing = Listing.objects.create(
            owner=self.owner,
            status=Listing.Status.ACTIVE,
            duration_days=7,
            active_from=now,
            active_until=now + timedelta(days=7),
            return_band=Listing.ReturnBand.R5_9,
        )

    def test_pledge_requires_login(self):
        url = reverse("investments:pledge", args=[self.listing.id])
        resp = self.client.post(url, data={"amount_gbp": "100.00"})
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse("users:login"), resp.url)

    def test_pledge_get_not_allowed(self):
        self.client.force_login(self.investor)
        url = reverse("investments:pledge", args=[self.listing.id])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 405)

    @patch("investments.views.get_return_pct_range", return_value=(Decimal("5"), Decimal("9")))
    def test_pledge_success_creates_investment_and_redirects_dashboard(self, mock_range):
        self.client.force_login(self.investor)

        url = reverse("investments:pledge", args=[self.listing.id])
        resp = self.client.post(url, data={"amount_gbp": "100.00"}, follow=True)

        self.assertEqual(Investment.objects.count(), 1)
        inv = Investment.objects.get()
        self.assertEqual(inv.amount_pence, 10000)

        # midpoint = 7%
        self.assertEqual(inv.expected_return_pence, 700)
        self.assertEqual(inv.expected_total_back_pence, 10700)
        self.assertEqual(inv.status, Investment.Status.PLEDGED)

        msgs = [m.message for m in get_messages(resp.wsgi_request)]
        self.assertTrue(any("Pledge created" in m for m in msgs))

        self.assertEqual(resp.redirect_chain[-1][0], reverse("users:dashboard"))

    def test_pledge_blocked_if_investing_own_listing_redirects_to_search(self):
        self.client.force_login(self.owner)

        url = reverse("investments:pledge", args=[self.listing.id])
        resp = self.client.post(url, data={"amount_gbp": "100.00"}, follow=True)

        self.assertEqual(Investment.objects.count(), 0)

        msgs = [m.message for m in get_messages(resp.wsgi_request)]
        self.assertTrue(any("cannot invest in your own listing" in m.lower() for m in msgs))

        self.assertEqual(resp.redirect_chain[-1][0], reverse("listings:search_listings"))

    def test_pledge_invalid_form_redirects_to_search(self):
        self.client.force_login(self.investor)

        url = reverse("investments:pledge", args=[self.listing.id])
        resp = self.client.post(url, data={"amount_gbp": "not-a-number"}, follow=True)

        self.assertEqual(Investment.objects.count(), 0)

        msgs = [m.message for m in get_messages(resp.wsgi_request)]
        self.assertTrue(any("enter a valid amount" in m.lower() for m in msgs))

        self.assertEqual(resp.redirect_chain[-1][0], reverse("listings:search_listings"))

    @patch("investments.views.get_return_pct_range", side_effect=Exception("bad band"))
    def test_pledge_invalid_return_band_redirects_to_search(self, mock_range):
        self.client.force_login(self.investor)

        url = reverse("investments:pledge", args=[self.listing.id])
        resp = self.client.post(url, data={"amount_gbp": "100.00"}, follow=True)

        self.assertEqual(Investment.objects.count(), 0)

        msgs = [m.message for m in get_messages(resp.wsgi_request)]
        self.assertTrue(any("valid return band" in m.lower() for m in msgs))

        self.assertEqual(resp.redirect_chain[-1][0], reverse("listings:search_listings"))

    @patch("investments.views.get_return_pct_range", return_value=(Decimal("5"), Decimal("9")))
    def test_pledge_listing_expired_redirects_to_search(self, mock_range):
        self.client.force_login(self.investor)

        self.listing.active_until = timezone.now() - timedelta(days=1)
        self.listing.save(update_fields=["active_until"])

        url = reverse("investments:pledge", args=[self.listing.id])
        resp = self.client.post(url, data={"amount_gbp": "100.00"}, follow=True)

        self.assertEqual(Investment.objects.count(), 0)

        msgs = [m.message for m in get_messages(resp.wsgi_request)]
        self.assertTrue(any("has expired" in m.lower() for m in msgs))

        self.assertEqual(resp.redirect_chain[-1][0], reverse("listings:search_listings"))

    def test_retract_requires_login(self):
        inv = Investment.objects.create(
            investor=self.investor,
            listing=self.listing,
            amount_pence=10000,
            expected_return_pence=700,
            expected_total_back_pence=10700,
            status=Investment.Status.PLEDGED,
        )

        url = reverse("investments:retract", args=[inv.id])
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse("users:login"), resp.url)

    def test_retract_success_sets_cancelled(self):
        inv = Investment.objects.create(
            investor=self.investor,
            listing=self.listing,
            amount_pence=10000,
            expected_return_pence=700,
            expected_total_back_pence=10700,
            status=Investment.Status.PLEDGED,
        )

        self.client.force_login(self.investor)
        url = reverse("investments:retract", args=[inv.id])
        resp = self.client.post(url, follow=True)

        inv.refresh_from_db()
        self.assertEqual(inv.status, Investment.Status.CANCELLED)

        msgs = [m.message for m in get_messages(resp.wsgi_request)]
        self.assertTrue(any("pledge retracted" in m.lower() for m in msgs))

        self.assertEqual(resp.redirect_chain[-1][0], reverse("users:dashboard"))

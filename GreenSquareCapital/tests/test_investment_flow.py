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
        # Create users for testing
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

        # Create an active listing with a valid time window
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
        # Pledge should redirect to login when user is not authenticated
        url = reverse("investments:pledge", args=[self.listing.id])
        resp = self.client.post(url, data={"amount_gbp": "100.00"})
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse("users:login"), resp.url)

    def test_pledge_get_not_allowed(self):
        # Pledge endpoint should be POST-only
        self.client.force_login(self.investor)
        url = reverse("investments:pledge", args=[self.listing.id])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 405)

    @patch("investments.views.get_return_pct_range", return_value=(Decimal("5"), Decimal("9")))
    def test_pledge_success_creates_investment_and_redirects_dashboard(self, mock_range):
        # Successful pledge creates an Investment and redirects to dashboard
        self.client.force_login(self.investor)

        url = reverse("investments:pledge", args=[self.listing.id])
        resp = self.client.post(url, data={"amount_gbp": "100.00"}, follow=True)

        # Investment record should be created with correct values
        self.assertEqual(Investment.objects.count(), 1)
        inv = Investment.objects.get()
        self.assertEqual(inv.amount_pence, 10000)

        # Expected return uses midpoint of band (5–9 -> 7%)
        self.assertEqual(inv.expected_return_pence, 700)
        self.assertEqual(inv.expected_total_back_pence, 10700)
        self.assertEqual(inv.status, Investment.Status.PLEDGED)

        # Success message should be added
        msgs = [m.message for m in get_messages(resp.wsgi_request)]
        self.assertTrue(any("Pledge created" in m for m in msgs))

        # Final redirect target should be dashboard
        self.assertEqual(resp.redirect_chain[-1][0], reverse("users:dashboard"))

    def test_pledge_blocked_if_investing_own_listing_redirects_to_search(self):
        # Owner should not be able to pledge on their own listing
        self.client.force_login(self.owner)

        url = reverse("investments:pledge", args=[self.listing.id])
        resp = self.client.post(url, data={"amount_gbp": "100.00"}, follow=True)

        # No investment should be created
        self.assertEqual(Investment.objects.count(), 0)

        # Error message should be shown
        msgs = [m.message for m in get_messages(resp.wsgi_request)]
        self.assertTrue(any("cannot invest in your own listing" in m.lower() for m in msgs))

        # Redirect back to search listings
        self.assertEqual(resp.redirect_chain[-1][0], reverse("listings:search_listings"))

    def test_pledge_invalid_form_redirects_to_search(self):
        # Invalid pledge form should not create an investment
        self.client.force_login(self.investor)

        url = reverse("investments:pledge", args=[self.listing.id])
        resp = self.client.post(url, data={"amount_gbp": "not-a-number"}, follow=True)

        # No investment should be created
        self.assertEqual(Investment.objects.count(), 0)

        # Validation message should be shown
        msgs = [m.message for m in get_messages(resp.wsgi_request)]
        self.assertTrue(any("enter a valid amount" in m.lower() for m in msgs))

        # Redirect back to search listings
        self.assertEqual(resp.redirect_chain[-1][0], reverse("listings:search_listings"))

    @patch("investments.views.get_return_pct_range", side_effect=Exception("bad band"))
    def test_pledge_invalid_return_band_redirects_to_search(self, mock_range):
        # If return calculation fails, pledge should be rejected and redirected
        self.client.force_login(self.investor)

        url = reverse("investments:pledge", args=[self.listing.id])
        resp = self.client.post(url, data={"amount_gbp": "100.00"}, follow=True)

        # No investment should be created
        self.assertEqual(Investment.objects.count(), 0)

        # Error message should be shown
        msgs = [m.message for m in get_messages(resp.wsgi_request)]
        self.assertTrue(any("valid return band" in m.lower() for m in msgs))

        # Redirect back to search listings
        self.assertEqual(resp.redirect_chain[-1][0], reverse("listings:search_listings"))

    @patch("investments.views.get_return_pct_range", return_value=(Decimal("5"), Decimal("9")))
    def test_pledge_listing_expired_redirects_to_search(self, mock_range):
        # Expired listings should block pledges
        self.client.force_login(self.investor)

        # Force listing to be expired
        self.listing.active_until = timezone.now() - timedelta(days=1)
        self.listing.save(update_fields=["active_until"])

        url = reverse("investments:pledge", args=[self.listing.id])
        resp = self.client.post(url, data={"amount_gbp": "100.00"}, follow=True)

        # No investment should be created
        self.assertEqual(Investment.objects.count(), 0)

        # Expiry message should be shown
        msgs = [m.message for m in get_messages(resp.wsgi_request)]
        self.assertTrue(any("has expired" in m.lower() for m in msgs))

        # Redirect back to search listings
        self.assertEqual(resp.redirect_chain[-1][0], reverse("listings:search_listings"))

    def test_retract_requires_login(self):
        # Create an existing pledge to retract
        inv = Investment.objects.create(
            investor=self.investor,
            listing=self.listing,
            amount_pence=10000,
            expected_return_pence=700,
            expected_total_back_pence=10700,
            status=Investment.Status.PLEDGED,
        )

        # Retract should redirect to login when user is not authenticated
        url = reverse("investments:retract", args=[inv.id])
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse("users:login"), resp.url)

    def test_retract_success_sets_cancelled(self):
        # Create an existing pledge to retract
        inv = Investment.objects.create(
            investor=self.investor,
            listing=self.listing,
            amount_pence=10000,
            expected_return_pence=700,
            expected_total_back_pence=10700,
            status=Investment.Status.PLEDGED,
        )

        # Retract as the investor
        self.client.force_login(self.investor)
        url = reverse("investments:retract", args=[inv.id])
        resp = self.client.post(url, follow=True)

        # Investment status should update to CANCELLED
        inv.refresh_from_db()
        self.assertEqual(inv.status, Investment.Status.CANCELLED)

        # Confirmation message should be shown
        msgs = [m.message for m in get_messages(resp.wsgi_request)]
        self.assertTrue(any("pledge retracted" in m.lower() for m in msgs))

        # Final redirect target should be dashboard
        self.assertEqual(resp.redirect_chain[-1][0], reverse("users:dashboard"))

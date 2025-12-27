from django.test import TestCase
from django.urls import reverse
from unittest.mock import patch

from django.conf import settings
from listings.models import Listing
from django.contrib.auth import get_user_model

User = get_user_model()


class StripeWebhookTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="owner", email="owner@example.com", password="Password123!"
        )
        self.listing = Listing.objects.create(
            owner=self.owner,
            status=Listing.Status.DRAFT,
            stripe_checkout_session_id="cs_test_123",
        )

    def test_webhook_returns_400_if_not_configured(self):
        url = reverse("listings:stripe_webhook")

        with self.settings(STRIPE_WEBHOOK_SECRET="", STRIPE_SECRET_KEY=""):
            resp = self.client.post(url, data=b"{}", content_type="application/json", HTTP_STRIPE_SIGNATURE="sig")
            self.assertEqual(resp.status_code, 400)

    @patch("listings.views.activate_listing_from_paid_session")
    @patch("listings.views.stripe.Webhook.construct_event")
    def test_webhook_activates_on_paid_session_completed(self, mock_construct, mock_activate):
        url = reverse("listings:stripe_webhook")

        event = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_123",
                    "payment_status": "paid",
                    "client_reference_id": str(self.listing.pk),
                    "metadata": {"listing_id": str(self.listing.pk)},
                }
            },
        }
        mock_construct.return_value = event

        with self.settings(STRIPE_WEBHOOK_SECRET="whsec_x", STRIPE_SECRET_KEY="sk_test_x"):
            resp = self.client.post(
                url,
                data=b"{}",
                content_type="application/json",
                HTTP_STRIPE_SIGNATURE="sig",
            )

        self.assertEqual(resp.status_code, 200)
        mock_activate.assert_called_once()

    @patch("listings.views.activate_listing_from_paid_session")
    @patch("listings.views.stripe.Webhook.construct_event")
    def test_webhook_ignores_unpaid(self, mock_construct, mock_activate):
        url = reverse("listings:stripe_webhook")

        event = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_123",
                    "payment_status": "unpaid",
                    "client_reference_id": str(self.listing.pk),
                }
            },
        }
        mock_construct.return_value = event

        with self.settings(STRIPE_WEBHOOK_SECRET="whsec_x", STRIPE_SECRET_KEY="sk_test_x"):
            resp = self.client.post(url, data=b"{}", content_type="application/json", HTTP_STRIPE_SIGNATURE="sig")

        self.assertEqual(resp.status_code, 200)
        mock_activate.assert_not_called()

    @patch("listings.views.activate_listing_from_paid_session")
    @patch("listings.views.stripe.Webhook.construct_event")
    def test_webhook_ignores_if_session_id_mismatch(self, mock_construct, mock_activate):
        url = reverse("listings:stripe_webhook")

        event = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_OTHER",
                    "payment_status": "paid",
                    "client_reference_id": str(self.listing.pk),
                }
            },
        }
        mock_construct.return_value = event

        with self.settings(STRIPE_WEBHOOK_SECRET="whsec_x", STRIPE_SECRET_KEY="sk_test_x"):
            resp = self.client.post(url, data=b"{}", content_type="application/json", HTTP_STRIPE_SIGNATURE="sig")

        self.assertEqual(resp.status_code, 200)
        mock_activate.assert_not_called()

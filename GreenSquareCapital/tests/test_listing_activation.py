from datetime import timedelta

from django.http import HttpResponse
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from unittest.mock import patch

from listings.models import Listing, ListingMedia

User = get_user_model()


class ListingActivationTests(TestCase):
    def setUp(self):
        # Create users for testing
        self.owner = User.objects.create_user(
            username="owner1", email="owner1@example.com", password="Password123!"
        )
        self.other_user = User.objects.create_user(
            username="other", email="other@example.com", password="Password123!"
        )

        # Create a draft listing
        self.listing = Listing.objects.create(
            owner=self.owner,
            status=Listing.Status.DRAFT,
            project_duration_days=30,
            source_use=Listing.UseType.RESIDENTIAL,
            target_use=Listing.UseType.RESIDENTIAL,
            funding_band=Listing.FundingBand.B10_20,
            return_type=Listing.ReturnType.PAYBACK,
            return_band=Listing.ReturnBand.R5_9,
            duration_days=7,
            country=Listing.Country.ENGLAND,
            county="Kent",
            postcode_prefix="CT",
        )

    def test_activate_requires_login(self):
        # Activation page should redirect to login when user is not authenticated
        url = reverse("listings:activate_listing", args=[self.listing.pk])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse("users:login"), resp.url)

    def test_activate_only_owner_can_access(self):
        # Non-owners should not be able to activate someone else’s listing
        self.client.force_login(self.other_user)
        url = reverse("listings:activate_listing", args=[self.listing.pk])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 404)

    def test_activate_only_draft_listings(self):
        # Active listings should not be re-activated
        self.listing.status = Listing.Status.ACTIVE
        now = timezone.now()
        self.listing.active_from = now
        self.listing.active_until = now + timedelta(days=7)
        self.listing.save()

        self.client.force_login(self.owner)
        url = reverse("listings:activate_listing", args=[self.listing.pk])
        resp = self.client.get(url, follow=True)

        # User should see a message and be redirected back to listing detail
        msgs = [m.message for m in get_messages(resp.wsgi_request)]
        self.assertTrue(any("only draft listings can be activated" in m.lower() for m in msgs))
        self.assertEqual(resp.redirect_chain[-1][0], reverse("listings:listing_detail", args=[self.listing.pk]))

    def test_activate_requires_ready_for_activation_including_media(self):
        # Listing must meet activation requirements
        self.client.force_login(self.owner)
        url = reverse("listings:activate_listing", args=[self.listing.pk])
        resp = self.client.get(url, follow=True)

        # User should be redirected to edit page with a guidance message
        msgs = [m.message for m in get_messages(resp.wsgi_request)]
        self.assertTrue(any("including at least one upload" in m.lower() for m in msgs))
        self.assertEqual(resp.redirect_chain[-1][0], reverse("listings:edit_listing", args=[self.listing.pk]))

    @patch("listings.views.start_listing_checkout_view", autospec=True)
    def test_activate_calls_checkout_when_ready(self, mock_checkout):
        # When listing is ready, activation should start the checkout flow
        mock_checkout.return_value = HttpResponse("ok")

        self.client.force_login(self.owner)

        # Add a media upload so the listing meets activation requirements
        upload = SimpleUploadedFile("pic.jpg", b"fake", content_type="image/jpeg")
        ListingMedia.objects.create(
            listing=self.listing,
            file=upload,
            media_type=ListingMedia.MediaType.IMAGE,
        )

        url = reverse("listings:activate_listing", args=[self.listing.pk])
        resp = self.client.get(url)

        # Checkout view should be called and response returned
        self.assertEqual(resp.status_code, 200)
        mock_checkout.assert_called_once()

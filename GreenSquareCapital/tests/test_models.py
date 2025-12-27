from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone

from investments.models import Investment
from listings.models import Listing, ListingMedia, listing_media_upload_to


User = get_user_model()


class InvestmentModelTests(TestCase):
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
        self.listing = Listing.objects.create(owner=self.owner)

    def test_pence_to_gbp_rounds_to_2dp(self):
        # 199p -> £1.99
        self.assertEqual(Investment._pence_to_gbp(199), Decimal("1.99"))

        # 1p -> £0.01
        self.assertEqual(Investment._pence_to_gbp(1), Decimal("0.01"))

        # 0p -> £0.00
        self.assertEqual(Investment._pence_to_gbp(0), Decimal("0.00"))

    def test_gbp_properties(self):
        inv = Investment.objects.create(
            investor=self.investor,
            listing=self.listing,
            amount_pence=12345,                # £123.45
            expected_return_pence=678,         # £6.78
            expected_total_back_pence=13023,   # £130.23
        )

        self.assertEqual(inv.amount_gbp, Decimal("123.45"))
        self.assertEqual(inv.expected_return_gbp, Decimal("6.78"))
        self.assertEqual(inv.expected_total_back_gbp, Decimal("130.23"))

    def test_default_status_is_pledged(self):
        inv = Investment.objects.create(
            investor=self.investor,
            listing=self.listing,
            amount_pence=1000,
        )
        self.assertEqual(inv.status, Investment.Status.PLEDGED)

    def test_str_includes_ids_and_amount(self):
        inv = Investment.objects.create(
            investor=self.investor,
            listing=self.listing,
            amount_pence=2500,  # £25.00
        )
        s = str(inv)
        self.assertIn(str(self.investor.id), s)
        self.assertIn(str(self.listing.id), s)
        self.assertIn("£25.00", s)


class ListingModelTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="owner1",
            email="owner1@example.com",
            password="Password123!",
        )

    def test_listing_active_days_safe_int(self):
        listing = Listing.objects.create(owner=self.owner, duration_days=None)
        self.assertEqual(listing.listing_active_days(), 0)

        listing.duration_days = 30
        self.assertEqual(listing.listing_active_days(), 30)

    def test_project_days_safe_int(self):
        listing = Listing.objects.create(owner=self.owner, project_duration_days=None)
        self.assertEqual(listing.project_days(), 0)

        listing.project_duration_days = 180
        self.assertEqual(listing.project_days(), 180)

    def test_total_price_pence_returns_0_when_no_duration(self):
        listing = Listing.objects.create(owner=self.owner, duration_days=None, price_per_day_pence=199)
        self.assertEqual(listing.total_price_pence(), 0)

    def test_total_price_pence_calculates_correctly(self):
        listing = Listing.objects.create(owner=self.owner, duration_days=10, price_per_day_pence=199)
        self.assertEqual(listing.total_price_pence(), 1990)

    def test_activate_raises_if_no_duration_days(self):
        listing = Listing.objects.create(owner=self.owner, duration_days=None)
        with self.assertRaises(ValueError):
            listing.activate()

    def test_activate_sets_status_and_dates(self):
        listing = Listing.objects.create(owner=self.owner, duration_days=7)

        before = timezone.now()
        listing.activate()
        after = timezone.now()

        listing.refresh_from_db()

        self.assertEqual(listing.status, Listing.Status.ACTIVE)
        self.assertIsNotNone(listing.active_from)
        self.assertIsNotNone(listing.active_until)

        # active_from should be "around now"
        self.assertTrue(before <= listing.active_from <= after)

        # active_until should be active_from + duration_days
        expected_until_start = listing.active_from + timedelta(days=7)
        # allow tiny differences due to save timing
        self.assertTrue(expected_until_start - timedelta(seconds=2) <= listing.active_until <= expected_until_start + timedelta(seconds=2))

    def test_str_uses_project_name_when_present(self):
        listing = Listing.objects.create(owner=self.owner, project_name="Old Police Station", status=Listing.Status.DRAFT)
        self.assertIn("Old Police Station", str(listing))
        self.assertIn("Draft", str(listing))

    def test_str_falls_back_to_listing_pk_when_no_project_name(self):
        listing = Listing.objects.create(owner=self.owner, project_name="", status=Listing.Status.DRAFT)
        s = str(listing)
        self.assertIn("Draft", s)
        # should contain "Listing <pk>"
        self.assertIn(f"Listing {listing.pk}", s)


class ListingMediaModelTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="owner1",
            email="owner1@example.com",
            password="Password123!",
        )
        self.listing = Listing.objects.create(owner=self.owner)

    def test_upload_path_function(self):
        media = ListingMedia(listing=self.listing, media_type=ListingMedia.MediaType.IMAGE)
        path = listing_media_upload_to(media, "photo.jpg")
        self.assertEqual(path, f"listing_media/listing_{self.listing.id}/photo.jpg")

    def test_str(self):
        uploaded = SimpleUploadedFile("doc.pdf", b"fake-pdf-bytes", content_type="application/pdf")
        media = ListingMedia.objects.create(
            listing=self.listing,
            media_type=ListingMedia.MediaType.DOCUMENT,
            file=uploaded,
        )
        self.assertIn("document", str(media).lower())
        self.assertIn(str(self.listing.id), str(media))

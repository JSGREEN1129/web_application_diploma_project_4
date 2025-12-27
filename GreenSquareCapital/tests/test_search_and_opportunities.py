from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from listings.models import Listing

User = get_user_model()


class SearchAndOpportunitiesTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="owner", email="owner@example.com", password="Password123!"
        )
        self.investor = User.objects.create_user(
            username="investor", email="investor@example.com", password="Password123!"
        )

        self.active = Listing.objects.create(
            owner=self.owner,
            status=Listing.Status.ACTIVE,
            project_name="Old Police Station",
            source_use=Listing.UseType.RESIDENTIAL,
            target_use=Listing.UseType.RESIDENTIAL,
            country=Listing.Country.ENGLAND,
            county="Kent",
            postcode_prefix="CT",
            funding_band=Listing.FundingBand.B10_20,
            return_type=Listing.ReturnType.PAYBACK,
            return_band=Listing.ReturnBand.R5_9,
            duration_days=7,
        )

        self.draft = Listing.objects.create(
            owner=self.owner,
            status=Listing.Status.DRAFT,
            project_name="Draft One",
        )

    def test_search_requires_login(self):
        url = reverse("listings:search_listings")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse("users:login"), resp.url)

    def test_search_shows_active_listings_excluding_own(self):
        self.client.force_login(self.investor)
        url = reverse("listings:search_listings")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

        listings = list(resp.context["page_obj"].object_list)
        self.assertIn(self.active, listings)
        self.assertNotIn(self.draft, listings)

    def test_search_excludes_listings_owned_by_request_user(self):
        self.client.force_login(self.owner)
        url = reverse("listings:search_listings")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

        listings = list(resp.context["page_obj"].object_list)
        self.assertNotIn(self.active, listings)

    def test_search_filters_by_project_name(self):
        self.client.force_login(self.investor)
        url = reverse("listings:search_listings")
        resp = self.client.get(url, {"project_name": "Police"})
        self.assertEqual(resp.status_code, 200)

        listings = list(resp.context["page_obj"].object_list)
        self.assertIn(self.active, listings)

        resp2 = self.client.get(url, {"project_name": "DoesNotExist"})
        listings2 = list(resp2.context["page_obj"].object_list)
        self.assertNotIn(self.active, listings2)

    def test_opportunity_detail_requires_login(self):
        url = reverse("listings:opportunity_detail", args=[self.active.pk])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse("users:login"), resp.url)

    def test_opportunity_detail_only_for_active(self):
        self.client.force_login(self.investor)

        url_active = reverse("listings:opportunity_detail", args=[self.active.pk])
        resp = self.client.get(url_active)
        self.assertEqual(resp.status_code, 200)

        url_draft = reverse("listings:opportunity_detail", args=[self.draft.pk])
        resp2 = self.client.get(url_draft)
        self.assertEqual(resp2.status_code, 404)

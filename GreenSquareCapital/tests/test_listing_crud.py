from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from listings.models import Listing, ListingMedia

User = get_user_model()


class ListingCrudTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="owner", email="owner@example.com", password="Password123!"
        )
        self.other = User.objects.create_user(
            username="other", email="other@example.com", password="Password123!"
        )

        self.listing = Listing.objects.create(
            owner=self.owner,
            status=Listing.Status.DRAFT,
            project_name="Draft A",
        )

    def test_listing_delete_requires_login(self):
        url = reverse("listings:listing_delete", args=[self.listing.pk])
        resp = self.client.post(url, data={"password": "Password123!"})
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse("users:login"), resp.url)

    def test_listing_delete_only_owner(self):
        self.client.force_login(self.other)
        url = reverse("listings:listing_delete", args=[self.listing.pk])
        resp = self.client.post(url, data={"password": "Password123!"})
        self.assertEqual(resp.status_code, 404)

    def test_listing_delete_requires_correct_password(self):
        self.client.force_login(self.owner)
        url = reverse("listings:listing_delete", args=[self.listing.pk])
        resp = self.client.post(url, data={"password": "WRONG"}, follow=True)

        self.assertTrue(Listing.objects.filter(pk=self.listing.pk).exists())
        msgs = [m.message for m in get_messages(resp.wsgi_request)]
        self.assertTrue(any("incorrect password" in m.lower() for m in msgs))

    def test_listing_delete_only_for_drafts(self):
        self.listing.status = Listing.Status.ACTIVE
        self.listing.save()

        self.client.force_login(self.owner)
        url = reverse("listings:listing_delete", args=[self.listing.pk])
        resp = self.client.post(url, data={"password": "Password123!"}, follow=True)

        self.assertTrue(Listing.objects.filter(pk=self.listing.pk).exists())
        msgs = [m.message for m in get_messages(resp.wsgi_request)]
        self.assertTrue(any("only draft listings can be deleted" in m.lower() for m in msgs))

    def test_listing_delete_removes_media_and_listing(self):
        self.client.force_login(self.owner)

        upload = SimpleUploadedFile("doc.pdf", b"fake", content_type="application/pdf")
        media = ListingMedia.objects.create(
            listing=self.listing,
            file=upload,
            media_type=ListingMedia.MediaType.DOCUMENT,
        )

        url = reverse("listings:listing_delete", args=[self.listing.pk])
        resp = self.client.post(url, data={"password": "Password123!"}, follow=True)

        self.assertFalse(Listing.objects.filter(pk=self.listing.pk).exists())
        self.assertFalse(ListingMedia.objects.filter(pk=media.pk).exists())

        msgs = [m.message for m in get_messages(resp.wsgi_request)]
        self.assertTrue(any("listing deleted" in m.lower() for m in msgs))

    def test_media_delete_requires_draft(self):
        self.client.force_login(self.owner)

        upload = SimpleUploadedFile("pic.jpg", b"fake", content_type="image/jpeg")
        media = ListingMedia.objects.create(
            listing=self.listing,
            file=upload,
            media_type=ListingMedia.MediaType.IMAGE,
        )

        self.listing.status = Listing.Status.ACTIVE
        self.listing.save()

        url = reverse("listings:listing_media_delete", args=[self.listing.pk, media.pk])
        resp = self.client.post(url, follow=True)

        self.assertTrue(ListingMedia.objects.filter(pk=media.pk).exists())
        msgs = [m.message for m in get_messages(resp.wsgi_request)]
        self.assertTrue(any("only draft listings can be edited" in m.lower() for m in msgs))

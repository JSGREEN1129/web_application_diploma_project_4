# Testing

> [!NOTE]
> Return back to the [README.md](/README.md) file.

### Python

I have used the [PEP8 Code Institute Validator](https://pep8ci.herokuapp.com/) to validate all of my py files.

| Directory | File | URL | Screenshot |
| --- | --- | --- | --- |
| listings | listings-forms.py | --- | ![screenshot](./documentation/test_reports/listings_app_linted/listings_forms_CI_linted.png) |
| listings | listings-models.py | --- | ![screenshot](./documentation/test_reports/listings_app_linted/listings_models_CI_linted.png) |
| listings | listings-urls.py | --- | ![screenshot](./documentation/test_reports/listings_app_linted/listings_urls_CI_linted.png) |
| listings | listings-views.py | --- | ![screenshot](./documentation/test_reports/listings_app_linted/listings_views_CI_linted.png) |
| users | users-forms.py | --- | ![screenshot](./documentation/test_reports/users_app_linted/users_forms_CI_linted.png) |
| users | users-views.py | --- | ![screenshot](./documentation/test_reports/users_app_linted/users_views_CI_linted.png) |
| users | users-backends.py | --- | ![screenshot](./documentation/test_reports/users_app_linted/users_backends_CI_linted.png) |

### CSS

I have used the [CSS Jigsaw Validator](https://jigsaw.w3.org/css-validator) to validate all of my CSS files.

| Directory | File | URL | Screenshot |
| --- | --- | --- | --- |
| static | assets/stylesheets/authentication.css | --- | ![screenshot](./documentation/test_reports/stylesheets_linted/authentication_css_linted.png) |
| static | assets/stylesheets/base.css | --- | ![screenshot](./documentation/test_reports/stylesheets_linted/base_css_linted.png) |
| static | assets/stylesheets/components.css | --- | ![screenshot](./documentation/test_reports/stylesheets_linted/components_css_linted.png) |
| static | assets/stylesheets/homepage.css | --- | ![screenshot](./documentation/test_reports/stylesheets_linted/dashboard_css_linted.png) |
| static | assets/stylesheets/homepage.css | --- | ![screenshot](./documentation/test_reports/stylesheets_linted/homepage_css_linted.png) |

## Responsiveness

I've tested my deployed project to check for responsiveness issues.

| Page | Mobile | Tablet | Desktop | Notes |
| --- | --- | --- | --- | --- |
| Homepage | ![screenshot](./documentation/responsive/gsc_homepage_responsive_mobile.png) | ![screenshot](./documentation/responsive/gsc_homepage_responsive_tablet.png) | ![screenshot](./documentation/responsive/gsc_homepage_responsive_desktop.png) | Works as expected |
| Login and Register | ![screenshot](./documentation/responsive/gsc_login_register_responsive_mobile_11.png) | ![screenshot](./documentation/responsive/gsc_login_register_responsive_tablet_11.png) | ![screenshot](./documentation/responsive/gsc_login_register_responsive_desktop_11.png) | Works as expected |
| Dashboard | ![screenshot](./documentation/responsive/gsc_dashboard_responsive_mobile.png) | ![screenshot](./documentation/responsive/gsc_dashboard_responsive_tablet.png) | ![screenshot](./documentation/responsive/gsc_dashboard_responsive_desktop.png) | Works as expected |
| Create Listing | ![screenshot](./documentation/responsive/gsc_create_listing_responsive_mobile.png) | ![screenshot](./documentation/responsive/gsc_create_listing_responsive_tablet.png) | ![screenshot](./documentation/responsive/gsc_create_listing_responsive_desktop.png) | Works as expected |
| Search Listing | ![screenshot](./documentation/responsive/gsc_search_listing_responsive_mobile.png) | ![screenshot](./documentation/responsive/gsc_search_listing_responsive_tablet.png) | ![screenshot](./documentation/responsive/gsc_search_listing_responsive_desktop.png) | Works as expected |
| View Listing | ![screenshot](./documentation/responsive/gsc_view_listing_responsive_mobile.png) | ![screenshot](./documentation/responsive/gsc_view_listing_responsive_tablet.png) | ![screenshot](./documentation/responsive/gsc_view_listing_responsive_desktop.png) | Works as expected |

## Browser Compatibility

I've tested my deployed project on multiple browsers to check for compatibility issues.

| Browser | Homepage | Login/Register | Projects |
| --- | --- | --- | --- |
| Google | ![screenshot](./documentation/browser/chrome_test.png) | ![screenshot](./documentation/browser/chrome_login_test.png) | ![screenshot](./documentation/browser/chrome_dashboard_test.png) | Works as expected |
| Firefox | ![screenshot](./documentation/browser/firefox_test.png) | ![screenshot](./documentation/browser/firefox_login_test.png) | ![screenshot](./documentation/browser/firefox_dashboard_test.png) | Works as expected |
| opera | ![screenshot](./documentation/browser/opera_test.png) | ![screenshot](./documentation/browser/opera_login_test.png) | ![screenshot](./documentation/browser/opera_dashboard_test.png) | Works as expected |

## Lighthouse Audit

| Page | Mobile | Desktop |
| --- | --- | --- |
| Homepage | ![screenshot](./documentation/lighthouse/mobile/gsc_lighthouse_homepage_mobile.png) | ![screenshot](./documentation/lighthouse/desktop/gsc_lighthouse_homepage_desktop.png) |
| Login and Register | ![screenshot](./documentation/lighthouse/mobile/gsc_lighthouse_login_register_mobile.png) | ![screenshot](./documentation/lighthouse/desktop/gsc_lighthouse_homepage_desktop.png) |
| Dashboard | ![screenshot](./documentation/lighthouse/mobile/gsc_lighthouse_dashboard_mobile.png) | ![screenshot](./documentation/lighthouse/desktop/gsc_lighthouse_homepage_desktop.png) |
| Create Listing | ![screenshot](./documentation/lighthouse/mobile/gsc_lighthouse_create_listing_mobile.png) | ![screenshot](./documentation/lighthouse/desktop/gsc_lighthouse_homepage_desktop.png) |
| Search Listings | ![screenshot](./documentation/lighthouse/mobile/gsc_lighthouse_search_listing_mobile.png) | ![screenshot](./documentation/lighthouse/desktop/gsc_lighthouse_homepage_desktop.png) |

# Testing Report

## Overview

I used my created test.py files to run application tests:

- **Total tests run:** 22 
- **Test duration:** ~59.36 seconds  
- **Test result:** 16 passed (OK) 6 skipped

## My tests.py files can be found on the following links :-
- **test_estimated_return** [test_estimate_return.py](./GreenSquareCapital/tests/test_estimate_return.py)
- **test_investment_flow** [test_investment_flow.py](./GreenSquareCapital/tests/test_investment_flow.py)
- **test_listing_activation** [test_listing_activation.py](./GreenSquareCapital/tests/test_listing_activation.py)
- **test_listing_crud** [test_listing_crud.py](./GreenSquareCapital/tests/test_listing_crud.py)
- **test_models** [test_models.py](./GreenSquareCapital/tests/test_models.py)
- **test_search_and_opportunities** [test_search_and_opportunities.py](./GreenSquareCapital/tests/test_search_and_opportunities.py)
- **test_stripe_webhook** [test_stripe_webhook.py](./GreenSquareCapital/tests/test_stripe_webhook.py)

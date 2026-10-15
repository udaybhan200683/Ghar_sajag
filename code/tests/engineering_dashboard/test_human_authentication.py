"""GS76-AUTH-H01..H14: injected-verifier tests, not production OIDC proof."""
from dataclasses import replace
import unittest

from ghar_sajag.human_authentication import (
    AuthenticationDenied, CurrentSession, HumanAuthenticationBoundary,
    IssuerPolicy, VerifiedAssertion,
)


ISSUER = "https://issuer.example.test/tenant"
AUDIENCE = "ghar-sajag-api"


class FixtureVerifier:
    def __init__(self, assertion):
        self.assertion = assertion
        self.error = None

    def verify(self, credential):
        if self.error:
            raise self.error
        return self.assertion if credential == "fixture-signed-credential" else None


class FixtureDirectory:
    def __init__(self, record):
        self.record = record
        self.error = None

    def current(self, issuer, subject, session_id):
        if self.error:
            raise self.error
        return self.record


class HumanAuthenticationTest(unittest.TestCase):
    def setUp(self):
        self.now = 100
        self.assertion = VerifiedAssertion(ISSUER, "stable-subject", (AUDIENCE,),
                                           "session-1", "access", 90, 90, 150)
        self.record = CurrentSession(ISSUER, "stable-subject", "session-1",
                                     "server-actor-1", True, True)
        self.verifier = FixtureVerifier(self.assertion)
        self.directory = FixtureDirectory(self.record)
        self.boundary = HumanAuthenticationBoundary(
            IssuerPolicy(ISSUER, AUDIENCE, "access"), self.verifier,
            self.directory, lambda: self.now)

    def denied(self, credential="fixture-signed-credential"):
        with self.assertRaises(AuthenticationDenied):
            self.boundary.authenticate(credential)

    def test_H01_maps_verified_subject_to_server_actor_without_role_or_home(self):
        result = self.boundary.authenticate("fixture-signed-credential")
        self.assertEqual(result.actor_id, "server-actor-1")
        self.assertEqual(result.session_id, "session-1")
        self.assertEqual(result.expires_at, 150)
        self.assertNotIn("stable-subject", result.issuer_reference)
        self.assertFalse(hasattr(result, "role"))
        self.assertFalse(hasattr(result, "home_id"))

    def test_H02_missing_dependencies_fail_closed(self):
        for verifier, directory in ((None, self.directory), (self.verifier, None)):
            boundary = HumanAuthenticationBoundary(self.boundary.policy, verifier,
                                                   directory, lambda: self.now)
            with self.assertRaises(AuthenticationDenied):
                boundary.authenticate("fixture-signed-credential")

    def test_H03_raw_claims_and_unknown_credentials_denied(self):
        for credential in (self.assertion, {"sub": "stable-subject"}, "unsigned", ""):
            self.denied(credential)

    def test_H04_wrong_issuer_audience_or_credential_use_denied(self):
        for changed in (dict(issuer="https://other.example.test"),
                        dict(audience=("other-api",)), dict(audience="ghar-sajag-api"),
                        dict(credential_kind="session")):
            self.verifier.assertion = replace(self.assertion, **changed)
            self.denied()

    def test_H05_expired_not_before_future_issued_at_and_invalid_time_denied(self):
        for changed in (dict(expires_at=100), dict(not_before=101),
                        dict(issued_at=101), dict(expires_at=True), dict(issued_at=-1)):
            self.verifier.assertion = replace(self.assertion, **changed)
            self.denied()
        self.verifier.assertion = self.assertion
        self.now = 150
        self.denied()

    def test_H06_offboarded_account_denied_with_still_valid_credential(self):
        self.directory.record = replace(self.record, account_active=False)
        self.denied()

    def test_H07_logout_revoked_session_denied_with_still_valid_credential(self):
        self.directory.record = replace(self.record, session_active=False)
        self.denied()

    def test_H08_stale_or_substituted_directory_binding_denied(self):
        for changed in (dict(issuer="https://other.example.test"),
                        dict(subject="another-person"), dict(session_id="old-session"),
                        dict(actor_id="")):
            self.directory.record = replace(self.record, **changed)
            self.denied()

    def test_H09_verifier_and_directory_outage_denied(self):
        self.verifier.error = RuntimeError("unavailable")
        self.denied()
        self.verifier.error = None
        self.directory.error = RuntimeError("unavailable")
        self.denied()

    def test_H10_fixture_does_not_install_service_or_diagnostic_route(self):
        from ghar_sajag.http_api import JsonApi
        self.assertEqual(JsonApi().dispatch("GET", "/v1/service/tickets", "",
                                            {}, {}),
                         ("404 Not Found", {"error": "route_not_found"}))

    def test_H11_issuer_policy_rejects_untrusted_or_ambiguous_configuration(self):
        for args in (("http://issuer.example.test", AUDIENCE, "access"),
                     (ISSUER, "", "access"), (ISSUER, AUDIENCE, "id")):
            with self.assertRaises(ValueError):
                IssuerPolicy(*args)

    def test_H12_rechecks_directory_on_every_request(self):
        self.boundary.authenticate("fixture-signed-credential")
        self.directory.record = replace(self.record, session_active=False)
        self.denied()

    def test_H13_malformed_verifier_result_denied(self):
        for result in (None, {"issuer": ISSUER}, "stable-subject"):
            self.verifier.assertion = result
            self.denied()

    def test_H14_expiry_during_authoritative_lookup_denied(self):
        def lookup(issuer, subject, session_id):
            self.now = 150
            return self.record
        self.directory.current = lookup
        self.denied()


if __name__ == "__main__":
    unittest.main()

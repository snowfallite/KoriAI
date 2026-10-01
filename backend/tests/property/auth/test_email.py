"""Email normalization (S1-05; tech.md §5.1 keeps emails in lower case)."""

from hypothesis import given
from hypothesis import strategies as st
from hypothesis.provisional import domains

from app.domains.auth.service import normalize_email

PADDING = st.sampled_from(["", " ", "\t", "\n", " \u00a0"])


@given(st.text())
def test_a_normalized_email_is_stable_lower_case_and_one_address(raw: str) -> None:
    email = normalize_email(raw)

    if email is not None:
        assert normalize_email(email) == email
        assert email == email.lower()
        assert email.count("@") == 1
        assert email.isprintable()  # no NUL or other control characters for Postgres text
        assert not any(char.isspace() for char in email)


@given(st.emails(domains=domains(max_length=63)), PADDING, PADDING)
def test_case_and_padding_of_an_address_do_not_matter(address: str, left: str, right: str) -> None:
    assert normalize_email(address) == address.lower()
    assert normalize_email(left + address.upper() + right) == address.lower()


@given(st.text(alphabet=st.characters(exclude_characters="@")))
def test_text_without_an_at_sign_is_not_an_email(raw: str) -> None:
    assert normalize_email(raw) is None

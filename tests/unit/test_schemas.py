"""
Unit tests for Pydantic schemas – request/response validation.
"""
import pytest
from pydantic import ValidationError

from app.schemas.auth import RegisterRequest, LoginRequest, TokenResponse, LogoutResponse
from app.schemas.book import BookCreate, BookUpdate, BookResponse, BookListResponse
from app.schemas.branch import BranchCreate, BranchUpdate, BranchResponse, BranchListResponse
from app.schemas.loan import LoanCreate, LoanStatusUpdate, LoanResponse, LoanListResponse
from app.schemas.user import UserResponse, UserUpdate, UserListResponse
from app.db.models import UserRole, LoanStatus


# ─── Auth schemas ───────────────────────────────────────────────


class TestRegisterRequest:
    def test_valid(self):
        req = RegisterRequest(email="a@b.com", password="123456", full_name="Test")
        assert req.email == "a@b.com"

    def test_invalid_email(self):
        with pytest.raises(ValidationError):
            RegisterRequest(email="not-email", password="123456", full_name="Test")

    def test_password_too_short(self):
        with pytest.raises(ValidationError):
            RegisterRequest(email="a@b.com", password="12345", full_name="Test")

    def test_password_too_long(self):
        with pytest.raises(ValidationError):
            RegisterRequest(email="a@b.com", password="x" * 129, full_name="Test")

    def test_empty_full_name(self):
        with pytest.raises(ValidationError):
            RegisterRequest(email="a@b.com", password="123456", full_name="")

    def test_missing_fields(self):
        with pytest.raises(ValidationError):
            RegisterRequest()


class TestLoginRequest:
    def test_valid(self):
        req = LoginRequest(email="a@b.com", password="pass")
        assert req.email == "a@b.com"

    def test_invalid_email(self):
        with pytest.raises(ValidationError):
            LoginRequest(email="bad", password="pass")


class TestTokenResponse:
    def test_default_token_type(self):
        t = TokenResponse(access_token="abc123")
        assert t.token_type == "bearer"


class TestLogoutResponse:
    def test_default_message(self):
        r = LogoutResponse()
        assert r.message == "Successfully logged out"


# ─── Book schemas ───────────────────────────────────────────────


class TestBookCreate:
    def test_valid(self):
        b = BookCreate(
            title="Test", author="Author", isbn="9781234567890",
            branch_id="branch-1",
        )
        assert b.total_copies == 1  # default

    def test_empty_title_rejected(self):
        with pytest.raises(ValidationError):
            BookCreate(title="", author="A", isbn="9781234567890", branch_id="b")

    def test_isbn_too_short(self):
        with pytest.raises(ValidationError):
            BookCreate(title="T", author="A", isbn="123", branch_id="b")

    def test_negative_copies_rejected(self):
        with pytest.raises(ValidationError):
            BookCreate(
                title="T", author="A", isbn="9781234567890",
                branch_id="b", total_copies=0,
            )

    def test_copies_must_be_at_least_one(self):
        b = BookCreate(
            title="T", author="A", isbn="9781234567890",
            branch_id="b", total_copies=1,
        )
        assert b.total_copies == 1


class TestBookUpdate:
    def test_all_optional(self):
        b = BookUpdate()
        assert b.title is None
        assert b.total_copies is None

    def test_partial_update(self):
        b = BookUpdate(title="New Title")
        assert b.title == "New Title"
        assert b.author is None

    def test_total_copies_can_be_zero(self):
        b = BookUpdate(total_copies=0)
        assert b.total_copies == 0


# ─── Branch schemas ─────────────────────────────────────────────


class TestBranchCreate:
    def test_valid(self):
        b = BranchCreate(name="Downtown", address="123 Main St")
        assert b.name == "Downtown"

    def test_empty_name_rejected(self):
        with pytest.raises(ValidationError):
            BranchCreate(name="", address="123 Main St")

    def test_empty_address_rejected(self):
        with pytest.raises(ValidationError):
            BranchCreate(name="Branch", address="")

    def test_optional_fields_default_none(self):
        b = BranchCreate(name="B", address="A")
        assert b.description is None
        assert b.phone_number is None
        assert b.email is None

    def test_invalid_email(self):
        with pytest.raises(ValidationError):
            BranchCreate(name="B", address="A", email="not-email")


class TestBranchUpdate:
    def test_all_optional(self):
        b = BranchUpdate()
        assert b.name is None
        assert b.is_active is None


# ─── Loan schemas ───────────────────────────────────────────────


class TestLoanCreate:
    def test_valid(self):
        lc = LoanCreate(book_id="book-1", branch_id="branch-1")
        assert lc.notes is None

    def test_with_notes(self):
        lc = LoanCreate(book_id="b", branch_id="br", notes="Urgent")
        assert lc.notes == "Urgent"

    def test_missing_book_id(self):
        with pytest.raises(ValidationError):
            LoanCreate(branch_id="br")

    def test_missing_branch_id(self):
        with pytest.raises(ValidationError):
            LoanCreate(book_id="b")


class TestLoanStatusUpdate:
    def test_valid_status(self):
        u = LoanStatusUpdate(status=LoanStatus.APPROVED)
        assert u.status == LoanStatus.APPROVED

    def test_invalid_status(self):
        with pytest.raises(ValidationError):
            LoanStatusUpdate(status="invalid_status")

    def test_with_notes(self):
        u = LoanStatusUpdate(status=LoanStatus.CANCELED, notes="Changed mind")
        assert u.notes == "Changed mind"


# ─── User schemas ───────────────────────────────────────────────


class TestUserUpdate:
    def test_all_optional(self):
        u = UserUpdate()
        assert u.email is None
        assert u.role is None

    def test_valid_role(self):
        u = UserUpdate(role=UserRole.LIBRARIAN)
        assert u.role == UserRole.LIBRARIAN

    def test_invalid_email(self):
        with pytest.raises(ValidationError):
            UserUpdate(email="bad")

    def test_password_too_short(self):
        with pytest.raises(ValidationError):
            UserUpdate(password="12345")

    def test_valid_password(self):
        u = UserUpdate(password="newpass123")
        assert u.password == "newpass123"


class TestUserResponse:
    def test_from_attributes(self):
        # Verify model_config allows from_attributes
        assert UserResponse.model_config.get("from_attributes") is True


class TestUserListResponse:
    def test_structure(self):
        resp = UserListResponse(items=[], total=0, page=1, size=20, pages=0)
        assert resp.items == []
        assert resp.total == 0


class TestBookListResponse:
    def test_structure(self):
        resp = BookListResponse(items=[], total=0, page=1, size=20, pages=0)
        assert resp.pages == 0


class TestBranchListResponse:
    def test_structure(self):
        resp = BranchListResponse(items=[], total=0, page=1, size=20, pages=0)
        assert resp.total == 0


class TestLoanListResponse:
    def test_structure(self):
        resp = LoanListResponse(items=[], total=0, page=1, size=20, pages=0)
        assert resp.size == 20


class TestBookResponseConfig:
    def test_from_attributes(self):
        assert BookResponse.model_config.get("from_attributes") is True


class TestBranchResponseConfig:
    def test_from_attributes(self):
        assert BranchResponse.model_config.get("from_attributes") is True


class TestLoanResponseConfig:
    def test_from_attributes(self):
        assert LoanResponse.model_config.get("from_attributes") is True


class TestRegisterRequestEdgeCases:
    def test_full_name_too_long(self):
        with pytest.raises(ValidationError):
            RegisterRequest(email="a@b.com", password="123456", full_name="X" * 256)



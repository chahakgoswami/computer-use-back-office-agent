"""Factory functions that build DOM trees for each mock portal page."""

from .dom import DOMNode, DOMDocument


def _input(name: str, input_type: str = "text", value: str = "",
           label: str = "", placeholder: str = "", required: bool = False,
           node_id: str = "") -> DOMNode:
    attrs = {
        "name": name,
        "type": input_type,
        "value": value,
        "placeholder": placeholder,
        "id": node_id or name,
    }
    if required:
        attrs["required"] = "required"
    wrapper = DOMNode(tag="div", attrs={"class": "field"})
    if label:
        wrapper.children.append(DOMNode(tag="label", text=label,
                                        attrs={"for": node_id or name}))
    wrapper.children.append(DOMNode(tag="input", attrs=attrs))
    return wrapper


def _select(name: str, options: list, label: str = "",
            node_id: str = "") -> DOMNode:
    attrs = {"name": name, "id": node_id or name}
    sel_node = DOMNode(tag="select", attrs=attrs)
    for opt_value, opt_label in options:
        sel_node.children.append(
            DOMNode(tag="option",
                    attrs={"value": opt_value},
                    text=opt_label)
        )
    wrapper = DOMNode(tag="div", attrs={"class": "field"})
    if label:
        wrapper.children.append(DOMNode(tag="label", text=label,
                                        attrs={"for": node_id or name}))
    wrapper.children.append(sel_node)
    return wrapper


def _checkbox(name: str, label: str = "", checked: bool = False,
              node_id: str = "") -> DOMNode:
    attrs = {"name": name, "type": "checkbox", "id": node_id or name}
    cb = DOMNode(tag="input", attrs=attrs)
    cb.checked = checked
    wrapper = DOMNode(tag="div", attrs={"class": "field"})
    if label:
        wrapper.children.append(DOMNode(tag="label", text=label,
                                        attrs={"for": node_id or name}))
    wrapper.children.append(cb)
    return wrapper


# ---------------------------------------------------------------------------
# Individual page builders
# ---------------------------------------------------------------------------

def build_login_page() -> DOMDocument:
    """Simulated login page with username / password fields."""
    body = DOMNode(tag="body")
    form = DOMNode(tag="form", attrs={"id": "login-form", "action": "/login",
                                      "method": "post"})
    form.children.append(
        DOMNode(tag="h1", text="Legacy Portal Login")
    )
    form.children.append(
        _input("username", label="Username", placeholder="Enter username",
               required=True)
    )
    form.children.append(
        _input("password", input_type="password", label="Password",
               placeholder="Enter password", required=True)
    )
    form.children.append(
        DOMNode(tag="button",
                attrs={"type": "submit", "id": "login-btn", "name": "login-btn"},
                text="Login")
    )
    body.children.append(form)
    root = DOMNode(tag="html")
    root.children.append(body)
    return DOMDocument(title="Login – Legacy Portal", root=root)


def build_dashboard_page(username: str = "user") -> DOMDocument:
    """Dashboard shown after successful login."""
    body = DOMNode(tag="body")
    body.children.append(
        DOMNode(tag="h1", text=f"Welcome, {username}!")
    )
    nav = DOMNode(tag="nav")
    for href, label in [
        ("/form", "Submit Form"),
        ("/upload", "Upload File"),
        ("/records", "View Records"),
        ("/logout", "Logout"),
    ]:
        link = DOMNode(tag="a", attrs={"href": href, "id": f"nav-{label.lower().replace(' ', '-')}"},
                       text=label)
        nav.children.append(link)
    body.children.append(nav)
    root = DOMNode(tag="html")
    root.children.append(body)
    return DOMDocument(title="Dashboard – Legacy Portal", root=root)


def build_form_page() -> DOMDocument:
    """Generic data-entry form with a variety of field types."""
    body = DOMNode(tag="body")
    form = DOMNode(tag="form", attrs={"id": "data-form", "action": "/form/submit",
                                      "method": "post"})
    form.children.append(DOMNode(tag="h1", text="Data Entry Form"))

    # Text fields
    form.children.append(
        _input("first_name", label="First Name", required=True)
    )
    form.children.append(
        _input("last_name", label="Last Name", required=True)
    )
    form.children.append(
        _input("email", input_type="email", label="Email", required=True)
    )
    form.children.append(
        _input("dob", input_type="date", label="Date of Birth")
    )

    # Dropdown
    form.children.append(
        _select("department", label="Department",
                options=[
                    ("", "-- Select --"),
                    ("hr", "Human Resources"),
                    ("eng", "Engineering"),
                    ("fin", "Finance"),
                    ("ops", "Operations"),
                ])
    )

    # Checkbox
    form.children.append(
        _checkbox("agree_terms", label="I agree to the terms and conditions")
    )

    # Textarea
    notes_wrapper = DOMNode(tag="div", attrs={"class": "field"})
    notes_wrapper.children.append(
        DOMNode(tag="label", text="Additional Notes", attrs={"for": "notes"})
    )
    notes_wrapper.children.append(
        DOMNode(tag="textarea", attrs={"name": "notes", "id": "notes",
                                       "rows": "4"})
    )
    form.children.append(notes_wrapper)

    # Hidden irreversible flag
    form.children.append(
        DOMNode(tag="input",
                attrs={"type": "hidden", "name": "irreversible",
                       "id": "irreversible", "value": "true"})
    )

    form.children.append(
        DOMNode(tag="button",
                attrs={"type": "submit", "id": "submit-btn", "name": "submit-btn"},
                text="Submit")
    )
    body.children.append(form)
    root = DOMNode(tag="html")
    root.children.append(body)
    return DOMDocument(title="Data Entry Form – Legacy Portal", root=root)


def build_upload_page() -> DOMDocument:
    """File-upload form page."""
    body = DOMNode(tag="body")
    form = DOMNode(tag="form", attrs={"id": "upload-form",
                                      "action": "/upload/submit",
                                      "method": "post",
                                      "enctype": "multipart/form-data"})
    form.children.append(DOMNode(tag="h1", text="File Upload"))
    form.children.append(
        _input("upload_file", input_type="file", label="Choose File",
               required=True)
    )
    form.children.append(
        _select("file_category", label="Category",
                options=[
                    ("", "-- Select --"),
                    ("report", "Report"),
                    ("invoice", "Invoice"),
                    ("contract", "Contract"),
                ])
    )
    form.children.append(
        DOMNode(tag="button",
                attrs={"type": "submit", "id": "upload-btn",
                       "name": "upload-btn"},
                text="Upload")
    )
    body.children.append(form)
    root = DOMNode(tag="html")
    root.children.append(body)
    return DOMDocument(title="File Upload – Legacy Portal", root=root)


def build_records_page(records: list = None) -> DOMDocument:
    """Simulated table of records extracted from the portal."""
    if records is None:
        records = [
            {"id": "REC-001", "name": "Alice Smith", "dept": "Engineering",
             "status": "Active"},
            {"id": "REC-002", "name": "Bob Jones", "dept": "Finance",
             "status": "Inactive"},
            {"id": "REC-003", "name": "Carol White", "dept": "HR",
             "status": "Active"},
        ]
    body = DOMNode(tag="body")
    body.children.append(DOMNode(tag="h1", text="Records"))
    table = DOMNode(tag="table", attrs={"id": "records-table"})

    # Header
    thead = DOMNode(tag="thead")
    tr_head = DOMNode(tag="tr")
    for col in ["ID", "Name", "Department", "Status"]:
        tr_head.children.append(DOMNode(tag="th", text=col))
    thead.children.append(tr_head)
    table.children.append(thead)

    # Body
    tbody = DOMNode(tag="tbody", attrs={"id": "records-body"})
    for rec in records:
        tr = DOMNode(tag="tr", attrs={"data-id": rec["id"]})
        for val in [rec["id"], rec["name"], rec["dept"], rec["status"]]:
            tr.children.append(DOMNode(tag="td", text=str(val)))
        tbody.children.append(tr)
    table.children.append(tbody)
    body.children.append(table)
    root = DOMNode(tag="html")
    root.children.append(body)
    return DOMDocument(title="Records – Legacy Portal", root=root)


def build_confirmation_page(message: str = "Action completed successfully.",
                             ref_id: str = "TXN-00001") -> DOMDocument:
    """Generic confirmation / success page."""
    body = DOMNode(tag="body")
    body.children.append(DOMNode(tag="h1", text="Confirmation"))
    body.children.append(
        DOMNode(tag="p", attrs={"id": "confirm-message"}, text=message)
    )
    body.children.append(
        DOMNode(tag="p",
                attrs={"id": "ref-id"},
                text=f"Reference ID: {ref_id}")
    )
    body.children.append(
        DOMNode(tag="a", attrs={"href": "/dashboard", "id": "back-link"},
                text="Back to Dashboard")
    )
    root = DOMNode(tag="html")
    root.children.append(body)
    return DOMDocument(title="Confirmation – Legacy Portal", root=root)


def build_error_page(message: str = "An error occurred.",
                     code: int = 500) -> DOMDocument:
    """Error page returned on invalid operations."""
    body = DOMNode(tag="body")
    body.children.append(
        DOMNode(tag="h1", text=f"Error {code}")
    )
    body.children.append(
        DOMNode(tag="p", attrs={"id": "error-message"}, text=message)
    )
    body.children.append(
        DOMNode(tag="a", attrs={"href": "/dashboard", "id": "back-link"},
                text="Back to Dashboard")
    )
    root = DOMNode(tag="html")
    root.children.append(body)
    return DOMDocument(title=f"Error {code} – Legacy Portal", root=root)

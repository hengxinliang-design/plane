# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import logging

from celery import shared_task
from django.core.mail import EmailMultiAlternatives, get_connection
from django.template.loader import render_to_string

from plane.db.models import IssueApprovalRequest
from plane.license.utils.instance_value import get_email_configuration
from plane.utils.email import generate_plain_text_from_html
from plane.utils.exception_logger import log_exception


def _issue_url(current_site, approval_request):
    if not current_site:
        return ""
    return (
        f"{current_site}/{approval_request.workspace.slug}/projects/"
        f"{approval_request.project_id}/issues/{approval_request.issue_id}"
    )


def _email_connection():
    (
        EMAIL_HOST,
        EMAIL_HOST_USER,
        EMAIL_HOST_PASSWORD,
        EMAIL_PORT,
        EMAIL_USE_TLS,
        EMAIL_USE_SSL,
        EMAIL_FROM,
    ) = get_email_configuration()

    connection = get_connection(
        host=EMAIL_HOST,
        port=int(EMAIL_PORT),
        username=EMAIL_HOST_USER,
        password=EMAIL_HOST_PASSWORD,
        use_tls=EMAIL_USE_TLS == "1",
        use_ssl=EMAIL_USE_SSL == "1",
    )
    return EMAIL_FROM, connection


@shared_task
def workflow_approval_requested_email(approval_request_id, current_site):
    try:
        approval_request = (
            IssueApprovalRequest.objects.select_related(
                "issue",
                "project",
                "workspace",
                "from_state",
                "to_state",
                "requested_by",
                "approver",
            )
            .filter(pk=approval_request_id)
            .first()
        )
        if not approval_request:
            return

        issue = approval_request.issue
        issue_url = _issue_url(current_site, approval_request)

        context = {
            "approver_name": approval_request.approver.first_name
            or approval_request.approver.display_name
            or approval_request.approver.email,
            "requester_name": approval_request.requested_by.first_name
            or approval_request.requested_by.display_name
            or approval_request.requested_by.email,
            "issue_name": issue.name,
            "issue_identifier": f"{approval_request.project.identifier}-{issue.sequence_id}",
            "project_name": approval_request.project.name,
            "workspace_name": approval_request.workspace.name,
            "from_state": approval_request.from_state.name,
            "to_state": approval_request.to_state.name,
            "issue_url": issue_url,
        }

        subject = (
            f"Approval requested for {context['issue_identifier']}: "
            f"{context['from_state']} -> {context['to_state']}"
        )
        html_content = render_to_string("emails/workflow/approval_requested.html", context)
        text_content = generate_plain_text_from_html(html_content)
        EMAIL_FROM, connection = _email_connection()
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=EMAIL_FROM,
            to=[approval_request.approver.email],
            connection=connection,
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send()
        logging.getLogger("plane.worker").info("Workflow approval request email sent successfully.")
        return
    except Exception as e:
        log_exception(e)
        return


@shared_task
def workflow_approval_responded_email(approval_request_id, current_site):
    try:
        approval_request = (
            IssueApprovalRequest.objects.select_related(
                "issue",
                "project",
                "workspace",
                "from_state",
                "to_state",
                "requested_by",
                "approver",
                "responded_by",
            )
            .filter(pk=approval_request_id)
            .first()
        )
        if not approval_request or approval_request.requested_by_id == approval_request.responded_by_id:
            return

        issue = approval_request.issue
        context = {
            "requester_name": approval_request.requested_by.first_name
            or approval_request.requested_by.display_name
            or approval_request.requested_by.email,
            "responder_name": approval_request.responded_by.first_name
            or approval_request.responded_by.display_name
            or approval_request.responded_by.email,
            "issue_name": issue.name,
            "issue_identifier": f"{approval_request.project.identifier}-{issue.sequence_id}",
            "project_name": approval_request.project.name,
            "workspace_name": approval_request.workspace.name,
            "from_state": approval_request.from_state.name,
            "to_state": approval_request.to_state.name,
            "status": approval_request.status,
            "response_message": approval_request.response_message,
            "issue_url": _issue_url(current_site, approval_request),
        }

        subject = f"Approval {approval_request.status} for {context['issue_identifier']}"
        html_content = render_to_string("emails/workflow/approval_responded.html", context)
        text_content = generate_plain_text_from_html(html_content)
        EMAIL_FROM, connection = _email_connection()
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=EMAIL_FROM,
            to=[approval_request.requested_by.email],
            connection=connection,
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send()
        logging.getLogger("plane.worker").info("Workflow approval response email sent successfully.")
        return
    except Exception as e:
        log_exception(e)
        return

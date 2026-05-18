# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.db import transaction
from rest_framework import status
from rest_framework.response import Response

from plane.bgtasks.workflow_approval_email_task import (
    workflow_approval_requested_email,
    workflow_approval_responded_email,
)
from plane.db.models import (
    IssueApprovalRequest,
    IssueAssignee,
    IssueWorkflowMember,
    ProjectMember,
    State,
    StateTransitionRule,
)
from plane.db.models.project import ROLE


def is_project_admin(user, project_id):
    return ProjectMember.objects.filter(
        project_id=project_id,
        member=user,
        role=ROLE.ADMIN.value,
        is_active=True,
    ).exists()


def get_issue_approver(issue):
    workflow_member = (
        IssueWorkflowMember.objects.filter(
            issue=issue,
            role_type=IssueWorkflowMember.RoleType.APPROVER,
        )
        .select_related("member")
        .first()
    )
    return workflow_member.member if workflow_member else None


def get_issue_workflow_role_members(issue):
    members = IssueWorkflowMember.objects.filter(issue=issue).values_list("role_type", "member_id")
    role_members = {
        StateTransitionRule.AllowedRole.APPROVER.value: set(),
        StateTransitionRule.AllowedRole.CO_WORKER.value: set(),
        StateTransitionRule.AllowedRole.ASSIGNEE.value: set(
            IssueAssignee.objects.filter(issue=issue, deleted_at__isnull=True).values_list("assignee_id", flat=True)
        ),
        StateTransitionRule.AllowedRole.CREATOR.value: {issue.created_by_id} if issue.created_by_id else set(),
    }
    for role_type, member_id in members:
        role_members.setdefault(role_type, set()).add(member_id)
    return role_members


def actor_can_directly_transition(issue, actor, rule):
    allowed_roles = rule.allowed_roles or [StateTransitionRule.AllowedRole.APPROVER.value]
    role_members = get_issue_workflow_role_members(issue)
    return any(actor.id in role_members.get(role, set()) for role in allowed_roles)


def validate_state_transition_or_request_approval(issue, requested_state_id, actor, current_site):
    if not requested_state_id or str(issue.state_id) == str(requested_state_id):
        return None

    to_state = State.objects.filter(project_id=issue.project_id, pk=requested_state_id).first()
    if not to_state:
        return Response(
            {"error": "State is not valid please pass a valid state_id"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    rule = StateTransitionRule.objects.filter(
        project_id=issue.project_id,
        from_state_id=issue.state_id,
        to_state=to_state,
    ).first()

    if is_project_admin(actor, issue.project_id):
        return None

    if not rule:
        return Response(
            {
                "error": "This state transition is not configured for the project workflow.",
                "transition_restricted": True,
                "missing_transition_rule": True,
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    if not rule.is_active:
        return Response(
            {
                "error": "This state transition is disabled for the project workflow.",
                "transition_restricted": True,
                "disabled_transition_rule": True,
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    if actor_can_directly_transition(issue, actor, rule):
        return None

    approver = get_issue_approver(issue)
    if not rule.requires_approval:
        return Response(
            {
                "error": "You are not allowed to perform this state transition.",
                "transition_restricted": True,
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    if not approver:
        return Response(
            {
                "error": "This state transition requires approval. Assign an Approver to this work item first.",
                "approval_required": True,
                "missing_approver": True,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    with transaction.atomic():
        approval_request, created = IssueApprovalRequest.objects.select_for_update().get_or_create(
            issue=issue,
            from_state=issue.state,
            to_state=to_state,
            status=IssueApprovalRequest.Status.PENDING,
            defaults={
                "project_id": issue.project_id,
                "workspace_id": issue.workspace_id,
                "rule": rule,
                "requested_by": actor,
                "approver": approver,
                "created_by": actor,
                "updated_by": actor,
            },
        )

        if not created and approval_request.approver_id != approver.id:
            approval_request.approver = approver
            approval_request.updated_by = actor
            approval_request.save(update_fields=["approver", "updated_by", "updated_at"])

    if created and rule.notify_enabled:
        workflow_approval_requested_email.delay(str(approval_request.id), current_site)

    return Response(
        {
            "approval_required": True,
            "approval_request_id": str(approval_request.id),
            "approver_id": str(approver.id),
            "detail": "Approval request created. The state was not changed.",
        },
        status=status.HTTP_202_ACCEPTED,
    )


def record_direct_approval_if_needed(issue, from_state_id, to_state_id, actor, current_site):
    if not to_state_id or str(from_state_id) == str(to_state_id):
        return

    rule = StateTransitionRule.objects.filter(
        project_id=issue.project_id,
        from_state_id=from_state_id,
        to_state_id=to_state_id,
        is_active=True,
        requires_approval=True,
    ).first()
    if not rule or is_project_admin(actor, issue.project_id):
        return

    approver = get_issue_approver(issue)
    if not approver or approver.id != actor.id:
        return

    from django.utils import timezone

    approval_request = IssueApprovalRequest.objects.filter(
        issue=issue,
        from_state_id=from_state_id,
        to_state_id=to_state_id,
        status=IssueApprovalRequest.Status.PENDING,
    ).first()

    if approval_request:
        approval_request.status = IssueApprovalRequest.Status.APPROVED
        approval_request.responded_by = actor
        approval_request.responded_at = timezone.now()
        approval_request.updated_by = actor
        approval_request.save(
            update_fields=["status", "responded_by", "responded_at", "updated_by", "updated_at"]
        )
        if rule.notify_enabled:
            workflow_approval_responded_email.delay(str(approval_request.id), current_site)
        return

    IssueApprovalRequest.objects.create(
        issue=issue,
        project_id=issue.project_id,
        workspace_id=issue.workspace_id,
        rule=rule,
        from_state_id=from_state_id,
        to_state_id=to_state_id,
        requested_by=actor,
        approver=actor,
        status=IssueApprovalRequest.Status.APPROVED,
        responded_by=actor,
        responded_at=timezone.now(),
        created_by=actor,
        updated_by=actor,
    )


def apply_approval_request(approval_request, actor, approve=True, response_message="", current_site=""):
    if approval_request.status != IssueApprovalRequest.Status.PENDING:
        return Response(
            {"error": "Approval request is not pending"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not (is_project_admin(actor, approval_request.project_id) or approval_request.approver_id == actor.id):
        return Response(
            {"error": "Only the assigned Approver or project Admin can respond to this approval request"},
            status=status.HTTP_403_FORBIDDEN,
        )

    with transaction.atomic():
        approval_request = IssueApprovalRequest.objects.select_for_update().select_related("issue").get(
            pk=approval_request.pk
        )
        if approval_request.status != IssueApprovalRequest.Status.PENDING:
            return Response(
                {"error": "Approval request is not pending"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if approve:
            issue = approval_request.issue
            issue.state = approval_request.to_state
            issue.updated_by = actor
            issue.save(update_fields=["state", "updated_by", "updated_at", "completed_at"])
            approval_request.status = IssueApprovalRequest.Status.APPROVED
        else:
            approval_request.status = IssueApprovalRequest.Status.REJECTED

        approval_request.response_message = response_message or ""
        approval_request.responded_by = actor
        approval_request.updated_by = actor

        from django.utils import timezone

        approval_request.responded_at = timezone.now()
        approval_request.save(
            update_fields=[
                "status",
                "response_message",
                "responded_by",
                "responded_at",
                "updated_by",
                "updated_at",
            ]
        )

    if approval_request.rule.notify_enabled:
        workflow_approval_responded_email.delay(str(approval_request.id), current_site)
    return None

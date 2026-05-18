# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.conf import settings
from django.db import models
from django.db.models import Q

from .project import ProjectBaseModel


class IssueWorkflowMember(ProjectBaseModel):
    class RoleType(models.TextChoices):
        APPROVER = "approver", "Approver"
        CO_WORKER = "co_worker", "Co-worker"

    issue = models.ForeignKey("db.Issue", on_delete=models.CASCADE, related_name="workflow_members")
    member = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="issue_workflow_memberships",
    )
    role_type = models.CharField(max_length=20, choices=RoleType.choices)

    class Meta:
        db_table = "issue_workflow_members"
        verbose_name = "Issue Workflow Member"
        verbose_name_plural = "Issue Workflow Members"
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=["issue", "member", "role_type"],
                condition=Q(deleted_at__isnull=True),
                name="issue_workflow_member_unique_active_role",
            ),
            models.UniqueConstraint(
                fields=["issue"],
                condition=Q(role_type="approver", deleted_at__isnull=True),
                name="issue_workflow_member_single_active_approver",
            ),
        ]

    def __str__(self):
        return f"{self.member_id} as {self.role_type} on {self.issue_id}"


class StateTransitionRule(ProjectBaseModel):
    class AllowedRole(models.TextChoices):
        APPROVER = "approver", "Approver"
        CO_WORKER = "co_worker", "Co-worker"
        ASSIGNEE = "assignee", "Assignee"
        CREATOR = "creator", "Creator"

    from_state = models.ForeignKey("db.State", on_delete=models.CASCADE, related_name="outgoing_transition_rules")
    to_state = models.ForeignKey("db.State", on_delete=models.CASCADE, related_name="incoming_transition_rules")
    allowed_roles = models.JSONField(default=list, blank=True)
    requires_approval = models.BooleanField(default=True)
    notify_enabled = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "state_transition_rules"
        verbose_name = "State Transition Rule"
        verbose_name_plural = "State Transition Rules"
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=["project", "from_state", "to_state"],
                condition=Q(deleted_at__isnull=True),
                name="state_transition_rule_unique_active_transition",
            ),
            models.CheckConstraint(
                check=~Q(from_state=models.F("to_state")),
                name="state_transition_rule_distinct_states",
            ),
        ]

    def __str__(self):
        return f"{self.project_id}: {self.from_state_id} -> {self.to_state_id}"


class IssueApprovalRequest(ProjectBaseModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"

    issue = models.ForeignKey("db.Issue", on_delete=models.CASCADE, related_name="approval_requests")
    rule = models.ForeignKey("db.StateTransitionRule", on_delete=models.CASCADE, related_name="approval_requests")
    from_state = models.ForeignKey("db.State", on_delete=models.CASCADE, related_name="approval_requests_from")
    to_state = models.ForeignKey("db.State", on_delete=models.CASCADE, related_name="approval_requests_to")
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="requested_issue_approvals",
    )
    approver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="assigned_issue_approvals",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    message = models.TextField(blank=True)
    response_message = models.TextField(blank=True)
    responded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="responded_issue_approvals",
    )
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "issue_approval_requests"
        verbose_name = "Issue Approval Request"
        verbose_name_plural = "Issue Approval Requests"
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=["issue", "from_state", "to_state"],
                condition=Q(status="pending", deleted_at__isnull=True),
                name="issue_approval_request_unique_pending_transition",
            ),
        ]

    def __str__(self):
        return f"{self.issue_id}: {self.from_state_id} -> {self.to_state_id} ({self.status})"

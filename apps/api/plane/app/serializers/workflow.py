# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from rest_framework import serializers

from .base import BaseSerializer
from .state import StateLiteSerializer
from .user import UserLiteSerializer
from plane.db.models import IssueApprovalRequest, IssueAssignee, IssueWorkflowMember, ProjectMember, State, StateTransitionRule
from plane.db.models.project import ROLE


class StateTransitionRuleSerializer(BaseSerializer):
    from_state_detail = StateLiteSerializer(read_only=True, source="from_state")
    to_state_detail = StateLiteSerializer(read_only=True, source="to_state")

    class Meta:
        model = StateTransitionRule
        fields = [
            "id",
            "project_id",
            "workspace_id",
            "from_state",
            "from_state_detail",
            "to_state",
            "to_state_detail",
            "allowed_roles",
            "requires_approval",
            "notify_enabled",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["workspace", "project", "created_at", "updated_at"]

    def validate(self, attrs):
        project_id = self.context.get("project_id")
        from_state = attrs.get("from_state", getattr(self.instance, "from_state", None))
        to_state = attrs.get("to_state", getattr(self.instance, "to_state", None))

        if from_state and to_state and from_state.id == to_state.id:
            raise serializers.ValidationError("From state and to state must be different")

        state_ids = [state.id for state in [from_state, to_state] if state]
        if state_ids and State.objects.filter(project_id=project_id, id__in=state_ids).count() != len(state_ids):
            raise serializers.ValidationError("States must belong to the project")

        allowed_roles = attrs.get("allowed_roles", getattr(self.instance, "allowed_roles", ["approver"]))
        valid_roles = {role.value for role in StateTransitionRule.AllowedRole}
        if allowed_roles is None:
            attrs["allowed_roles"] = []
        elif not isinstance(allowed_roles, list):
            raise serializers.ValidationError({"allowed_roles": "Allowed roles must be a list"})
        else:
            invalid_roles = [role for role in allowed_roles if role not in valid_roles]
            if invalid_roles:
                raise serializers.ValidationError({"allowed_roles": f"Invalid roles: {invalid_roles}"})
            attrs["allowed_roles"] = list(dict.fromkeys(allowed_roles))

        return attrs


class IssueWorkflowMemberSerializer(BaseSerializer):
    member_detail = UserLiteSerializer(read_only=True, source="member")

    class Meta:
        model = IssueWorkflowMember
        fields = [
            "id",
            "issue_id",
            "project_id",
            "workspace_id",
            "member",
            "member_detail",
            "role_type",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["workspace", "project", "issue", "created_at", "updated_at"]


class IssueWorkflowMemberUpdateSerializer(serializers.Serializer):
    approver_id = serializers.UUIDField(required=False, allow_null=True)
    co_worker_ids = serializers.ListField(child=serializers.UUIDField(), required=False)

    def validate(self, attrs):
        project_id = self.context["project_id"]
        issue = self.context.get("issue")
        if "co_worker_ids" in attrs:
            attrs["co_worker_ids"] = list(dict.fromkeys(attrs["co_worker_ids"]))

        if attrs.get("approver_id") and attrs["approver_id"] in attrs.get("co_worker_ids", []):
            raise serializers.ValidationError({"members": "Approver cannot also be a Co-worker on the same work item"})

        user_ids = []
        if attrs.get("approver_id"):
            user_ids.append(attrs["approver_id"])
        user_ids.extend(attrs.get("co_worker_ids", []))

        if not user_ids:
            return attrs

        valid_member_ids = set(
            ProjectMember.objects.filter(
                project_id=project_id,
                member_id__in=user_ids,
                role__gte=ROLE.MEMBER.value,
                is_active=True,
            ).values_list("member_id", flat=True)
        )

        invalid_user_ids = [str(user_id) for user_id in user_ids if user_id not in valid_member_ids]
        if invalid_user_ids:
            raise serializers.ValidationError({"members": f"Users are not active project members: {invalid_user_ids}"})

        if issue:
            assignee_ids = set(
                IssueAssignee.objects.filter(issue=issue, deleted_at__isnull=True).values_list("assignee_id", flat=True)
            )
            assigned_workflow_user_ids = [str(user_id) for user_id in user_ids if user_id in assignee_ids]
            if assigned_workflow_user_ids:
                raise serializers.ValidationError(
                    {"members": f"Assignees cannot be Approver or Co-worker: {assigned_workflow_user_ids}"}
                )

        project_members = {
            project_member.member_id: project_member.workflow_roles or []
            for project_member in ProjectMember.objects.filter(
                project_id=project_id,
                member_id__in=user_ids,
                role__gte=ROLE.MEMBER.value,
                is_active=True,
            )
        }

        invalid_approvers = []
        if attrs.get("approver_id") and ProjectMember.WorkflowRole.APPROVER not in project_members.get(
            attrs["approver_id"], []
        ):
            invalid_approvers.append(str(attrs["approver_id"]))

        invalid_co_workers = [
            str(user_id)
            for user_id in attrs.get("co_worker_ids", [])
            if ProjectMember.WorkflowRole.CO_WORKER not in project_members.get(user_id, [])
        ]
        if invalid_approvers or invalid_co_workers:
            errors = {}
            if invalid_approvers:
                errors["approver_id"] = f"Users do not have the Approver project role: {invalid_approvers}"
            if invalid_co_workers:
                errors["co_worker_ids"] = f"Users do not have the Co-worker project role: {invalid_co_workers}"
            raise serializers.ValidationError(errors)

        return attrs


class IssueApprovalRequestSerializer(BaseSerializer):
    from_state_detail = StateLiteSerializer(read_only=True, source="from_state")
    to_state_detail = StateLiteSerializer(read_only=True, source="to_state")
    requested_by_detail = UserLiteSerializer(read_only=True, source="requested_by")
    approver_detail = UserLiteSerializer(read_only=True, source="approver")
    responded_by_detail = UserLiteSerializer(read_only=True, source="responded_by")

    class Meta:
        model = IssueApprovalRequest
        fields = [
            "id",
            "issue_id",
            "project_id",
            "workspace_id",
            "rule",
            "from_state",
            "from_state_detail",
            "to_state",
            "to_state_detail",
            "requested_by",
            "requested_by_detail",
            "approver",
            "approver_detail",
            "status",
            "message",
            "response_message",
            "responded_by",
            "responded_by_detail",
            "responded_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

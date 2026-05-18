# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from rest_framework import status
from rest_framework.response import Response

from plane.app.permissions import ROLE, allow_permission
from plane.app.serializers import (
    IssueApprovalRequestSerializer,
    IssueWorkflowMemberSerializer,
    IssueWorkflowMemberUpdateSerializer,
    StateTransitionRuleSerializer,
)
from .base import BaseAPIView, BaseViewSet
from plane.db.models import Issue, IssueApprovalRequest, IssueWorkflowMember, StateTransitionRule
from plane.utils.host import base_host
from plane.utils.workflow_approval import apply_approval_request


class StateTransitionRuleViewSet(BaseViewSet):
    model = StateTransitionRule
    serializer_class = StateTransitionRuleSerializer

    def get_queryset(self):
        return self.filter_queryset(
            super()
            .get_queryset()
            .filter(
                workspace__slug=self.kwargs.get("slug"),
                project_id=self.kwargs.get("project_id"),
            )
            .select_related("from_state", "to_state", "project", "workspace")
        )

    @allow_permission([ROLE.ADMIN])
    def list(self, request, slug, project_id):
        serializer = StateTransitionRuleSerializer(self.get_queryset(), many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @allow_permission([ROLE.ADMIN])
    def create(self, request, slug, project_id):
        serializer = StateTransitionRuleSerializer(data=request.data, context={"project_id": project_id})
        if serializer.is_valid():
            serializer.save(project_id=project_id, created_by=request.user, updated_by=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @allow_permission([ROLE.ADMIN])
    def partial_update(self, request, slug, project_id, pk):
        rule = self.get_queryset().filter(pk=pk).first()
        if not rule:
            return Response({"error": "Transition rule not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = StateTransitionRuleSerializer(
            rule,
            data=request.data,
            partial=True,
            context={"project_id": project_id},
        )
        if serializer.is_valid():
            serializer.save(updated_by=request.user)
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @allow_permission([ROLE.ADMIN])
    def destroy(self, request, slug, project_id, pk):
        rule = self.get_queryset().filter(pk=pk).first()
        if not rule:
            return Response({"error": "Transition rule not found"}, status=status.HTTP_404_NOT_FOUND)
        rule.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class IssueWorkflowMemberEndpoint(BaseAPIView):
    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def get(self, request, slug, project_id, issue_id):
        issue = Issue.objects.filter(workspace__slug=slug, project_id=project_id, pk=issue_id).first()
        if not issue:
            return Response({"error": "Issue not found"}, status=status.HTTP_404_NOT_FOUND)

        members = IssueWorkflowMember.objects.filter(issue=issue).select_related("member")
        approver = members.filter(role_type=IssueWorkflowMember.RoleType.APPROVER).first()
        co_workers = members.filter(role_type=IssueWorkflowMember.RoleType.CO_WORKER)

        return Response(
            {
                "approver": IssueWorkflowMemberSerializer(approver).data if approver else None,
                "co_workers": IssueWorkflowMemberSerializer(co_workers, many=True).data,
            },
            status=status.HTTP_200_OK,
        )

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def patch(self, request, slug, project_id, issue_id):
        issue = Issue.objects.filter(workspace__slug=slug, project_id=project_id, pk=issue_id).first()
        if not issue:
            return Response({"error": "Issue not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = IssueWorkflowMemberUpdateSerializer(
            data=request.data,
            context={"project_id": project_id, "issue": issue},
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        if "approver_id" in data:
            IssueWorkflowMember.objects.filter(
                issue=issue,
                role_type=IssueWorkflowMember.RoleType.APPROVER,
            ).delete()
            if data["approver_id"]:
                IssueWorkflowMember.objects.create(
                    issue=issue,
                    project_id=project_id,
                    workspace_id=issue.workspace_id,
                    member_id=data["approver_id"],
                    role_type=IssueWorkflowMember.RoleType.APPROVER,
                    created_by=request.user,
                    updated_by=request.user,
                )

        if "co_worker_ids" in data:
            IssueWorkflowMember.objects.filter(
                issue=issue,
                role_type=IssueWorkflowMember.RoleType.CO_WORKER,
            ).delete()
            IssueWorkflowMember.objects.bulk_create(
                [
                    IssueWorkflowMember(
                        issue=issue,
                        project_id=project_id,
                        workspace_id=issue.workspace_id,
                        member_id=member_id,
                        role_type=IssueWorkflowMember.RoleType.CO_WORKER,
                        created_by=request.user,
                        updated_by=request.user,
                    )
                    for member_id in data["co_worker_ids"]
                ],
                batch_size=25,
            )

        members = IssueWorkflowMember.objects.filter(issue=issue).select_related("member")
        approver = members.filter(role_type=IssueWorkflowMember.RoleType.APPROVER).first()
        co_workers = members.filter(role_type=IssueWorkflowMember.RoleType.CO_WORKER)

        return Response(
            {
                "approver": IssueWorkflowMemberSerializer(approver).data if approver else None,
                "co_workers": IssueWorkflowMemberSerializer(co_workers, many=True).data,
            },
            status=status.HTTP_200_OK,
        )


class IssueApprovalRequestViewSet(BaseViewSet):
    model = IssueApprovalRequest
    serializer_class = IssueApprovalRequestSerializer

    def get_queryset(self):
        return self.filter_queryset(
            super()
            .get_queryset()
            .filter(
                workspace__slug=self.kwargs.get("slug"),
                project_id=self.kwargs.get("project_id"),
            )
            .select_related(
                "issue",
                "from_state",
                "to_state",
                "requested_by",
                "approver",
                "responded_by",
            )
        )

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def list(self, request, slug, project_id, issue_id=None):
        queryset = self.get_queryset()
        if issue_id:
            queryset = queryset.filter(issue_id=issue_id)
        serializer = IssueApprovalRequestSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def approve(self, request, slug, project_id, pk):
        approval_request = self.get_queryset().filter(pk=pk).first()
        if not approval_request:
            return Response({"error": "Approval request not found"}, status=status.HTTP_404_NOT_FOUND)

        response = apply_approval_request(
            approval_request,
            request.user,
            approve=True,
            response_message=request.data.get("response_message", ""),
            current_site=base_host(request=request, is_app=True),
        )
        if response:
            return response

        approval_request.refresh_from_db()
        return Response(IssueApprovalRequestSerializer(approval_request).data, status=status.HTTP_200_OK)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def reject(self, request, slug, project_id, pk):
        approval_request = self.get_queryset().filter(pk=pk).first()
        if not approval_request:
            return Response({"error": "Approval request not found"}, status=status.HTTP_404_NOT_FOUND)

        response = apply_approval_request(
            approval_request,
            request.user,
            approve=False,
            response_message=request.data.get("response_message", ""),
            current_site=base_host(request=request, is_app=True),
        )
        if response:
            return response

        approval_request.refresh_from_db()
        return Response(IssueApprovalRequestSerializer(approval_request).data, status=status.HTTP_200_OK)

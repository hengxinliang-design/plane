# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.urls import path

from plane.app.views import IssueApprovalRequestViewSet, IssueWorkflowMemberEndpoint, StateTransitionRuleViewSet


urlpatterns = [
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/state-transition-rules/",
        StateTransitionRuleViewSet.as_view({"get": "list", "post": "create"}),
        name="state-transition-rules",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/state-transition-rules/<uuid:pk>/",
        StateTransitionRuleViewSet.as_view({"patch": "partial_update", "delete": "destroy"}),
        name="state-transition-rule-detail",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/issues/<uuid:issue_id>/workflow-members/",
        IssueWorkflowMemberEndpoint.as_view(),
        name="issue-workflow-members",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/issues/<uuid:issue_id>/approval-requests/",
        IssueApprovalRequestViewSet.as_view({"get": "list"}),
        name="issue-approval-requests",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/approval-requests/",
        IssueApprovalRequestViewSet.as_view({"get": "list"}),
        name="project-approval-requests",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/approval-requests/<uuid:pk>/approve/",
        IssueApprovalRequestViewSet.as_view({"post": "approve"}),
        name="issue-approval-request-approve",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/approval-requests/<uuid:pk>/reject/",
        IssueApprovalRequestViewSet.as_view({"post": "reject"}),
        name="issue-approval-request-reject",
    ),
]

# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import pytest
from rest_framework import status

from plane.db.models import (
    Issue,
    IssueAssignee,
    IssueWorkflowMember,
    Project,
    ProjectMember,
    State,
    Workspace,
    WorkspaceMember,
)
from plane.tests.factories import UserFactory


@pytest.mark.contract
class TestWorkspaceUserProfileIssuesAPI:
    @pytest.mark.django_db
    def test_assigned_profile_view_includes_assignee_and_approver_issues(self, api_client):
        target_user = UserFactory(email="target-user@plane.so")
        creator = UserFactory(email="creator@plane.so")

        workspace = Workspace.objects.create(name="Profile Workspace", slug="profile-workspace", owner=creator)
        WorkspaceMember.objects.create(workspace=workspace, member=target_user, role=15)
        WorkspaceMember.objects.create(workspace=workspace, member=creator, role=20)

        project = Project.objects.create(
            name="Profile Project",
            identifier="PROF",
            workspace=workspace,
            created_by=creator,
            updated_by=creator,
        )
        ProjectMember.objects.create(project=project, member=target_user, role=15)
        ProjectMember.objects.create(project=project, member=creator, role=20)

        state = State.objects.create(
            name="Todo",
            color="#60646C",
            group="unstarted",
            default=True,
            project=project,
        )

        parent_issue = Issue.objects.create(
            name="Parent issue",
            project=project,
            state=state,
            created_by=creator,
        )

        assignee_issue = Issue.objects.create(
            name="Assignee issue",
            project=project,
            state=state,
            created_by=creator,
            parent=parent_issue,
        )
        IssueAssignee.objects.create(issue=assignee_issue, assignee=target_user, project=project)

        approver_issue = Issue.objects.create(
            name="Approver issue",
            project=project,
            state=state,
            created_by=creator,
            parent=parent_issue,
        )
        IssueWorkflowMember.objects.create(
            issue=approver_issue,
            member=target_user,
            role_type=IssueWorkflowMember.RoleType.APPROVER,
            project=project,
        )

        unrelated_issue = Issue.objects.create(
            name="Unrelated issue",
            project=project,
            state=state,
            created_by=creator,
        )

        api_client.force_authenticate(user=target_user)

        response = api_client.get(
            f"/api/workspaces/{workspace.slug}/user-issues/{target_user.id}/",
            {
                "group_by": "state_id",
                "order_by": "sort_order",
                "sub_issue": "false",
                "filters": "{}",
                "layout": "list",
                "cursor": "50:0:0",
                "per_page": "50",
                "assignees": str(target_user.id),
            },
        )

        assert response.status_code == status.HTTP_200_OK
        returned_issue_ids = {
            str(issue["id"])
            for group in response.data["results"].values()
            for issue in group["results"]
        }

        assert str(assignee_issue.id) in returned_issue_ids
        assert str(approver_issue.id) in returned_issue_ids
        assert str(unrelated_issue.id) not in returned_issue_ids
        assert response.data["total_count"] == 2

    @pytest.mark.django_db
    def test_assigned_profile_priority_group_includes_sub_issues(self, api_client):
        target_user = UserFactory(email="target-priority@plane.so")
        creator = UserFactory(email="priority-creator@plane.so")

        workspace = Workspace.objects.create(name="Priority Workspace", slug="priority-workspace", owner=creator)
        WorkspaceMember.objects.create(workspace=workspace, member=target_user, role=15)
        WorkspaceMember.objects.create(workspace=workspace, member=creator, role=20)

        project = Project.objects.create(
            name="Priority Project",
            identifier="PRIO",
            workspace=workspace,
            created_by=creator,
            updated_by=creator,
        )
        ProjectMember.objects.create(project=project, member=target_user, role=15)
        ProjectMember.objects.create(project=project, member=creator, role=20)

        state = State.objects.create(
            name="Todo",
            color="#60646C",
            group="unstarted",
            default=True,
            project=project,
        )
        parent_issue = Issue.objects.create(
            name="Parent issue",
            project=project,
            state=state,
            created_by=creator,
        )
        assigned_sub_issue = Issue.objects.create(
            name="Assigned sub issue",
            project=project,
            state=state,
            priority="none",
            created_by=creator,
            parent=parent_issue,
        )
        IssueAssignee.objects.create(issue=assigned_sub_issue, assignee=target_user, project=project)

        api_client.force_authenticate(user=target_user)

        response = api_client.get(
            f"/api/workspaces/{workspace.slug}/user-issues/{target_user.id}/",
            {
                "group_by": "priority",
                "order_by": "sort_order",
                "sub_issue": "false",
                "filters": "{}",
                "layout": "list",
                "cursor": "50:0:0",
                "per_page": "50",
                "assignees": str(target_user.id),
            },
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["total_count"] == 1
        returned_issue_ids = {
            str(issue["id"])
            for group in response.data["results"].values()
            for issue in group["results"]
        }
        assert str(assigned_sub_issue.id) in returned_issue_ids

    @pytest.mark.django_db
    def test_created_profile_view_only_includes_created_issues(self, api_client):
        target_user = UserFactory(email="target-creator@plane.so")
        other_user = UserFactory(email="other-user@plane.so")

        workspace = Workspace.objects.create(name="Created Workspace", slug="created-workspace", owner=target_user)
        WorkspaceMember.objects.create(workspace=workspace, member=target_user, role=15)
        WorkspaceMember.objects.create(workspace=workspace, member=other_user, role=15)

        project = Project.objects.create(
            name="Created Project",
            identifier="CRTD",
            workspace=workspace,
            created_by=target_user,
            updated_by=target_user,
        )
        ProjectMember.objects.create(project=project, member=target_user, role=15)
        ProjectMember.objects.create(project=project, member=other_user, role=15)

        state = State.objects.create(
            name="Todo",
            color="#60646C",
            group="unstarted",
            default=True,
            project=project,
        )

        created_issue = Issue.objects.create(
            name="Created by target",
            project=project,
            state=state,
            created_by=target_user,
        )
        assigned_but_not_created = Issue.objects.create(
            name="Assigned but not created",
            project=project,
            state=state,
            created_by=other_user,
        )
        IssueAssignee.objects.create(issue=assigned_but_not_created, assignee=target_user, project=project)

        api_client.force_authenticate(user=target_user)

        response = api_client.get(
            f"/api/workspaces/{workspace.slug}/user-issues/{target_user.id}/",
            {
                "group_by": "state_id",
                "order_by": "sort_order",
                "sub_issue": "false",
                "filters": "{}",
                "layout": "list",
                "cursor": "50:0:0",
                "per_page": "50",
                "created_by": str(target_user.id),
            },
        )

        assert response.status_code == status.HTTP_200_OK
        returned_issue_ids = {
            str(issue["id"])
            for group in response.data["results"].values()
            for issue in group["results"]
        }

        assert str(created_issue.id) in returned_issue_ids
        assert str(assigned_but_not_created.id) not in returned_issue_ids
        assert response.data["total_count"] == 1

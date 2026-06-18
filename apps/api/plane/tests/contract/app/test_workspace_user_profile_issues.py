# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import pytest
from rest_framework import status

from plane.db.models import (
    Issue,
    IssueAssignee,
    IssueSubscriber,
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
    def test_setting_co_worker_subscribes_member_to_issue(self, api_client):
        co_worker = UserFactory(email="co-worker@plane.so", username="co-worker")
        second_co_worker = UserFactory(email="second-co-worker@plane.so", username="second-co-worker")
        creator = UserFactory(email="workflow-creator@plane.so", username="workflow-creator")

        workspace = Workspace.objects.create(name="Workflow Workspace", slug="workflow-workspace", owner=creator)
        WorkspaceMember.objects.create(workspace=workspace, member=co_worker, role=15)
        WorkspaceMember.objects.create(workspace=workspace, member=second_co_worker, role=15)
        WorkspaceMember.objects.create(workspace=workspace, member=creator, role=20)

        project = Project.objects.create(
            name="Workflow Project",
            identifier="FLOW",
            workspace=workspace,
            created_by=creator,
            updated_by=creator,
        )
        ProjectMember.objects.create(
            project=project,
            member=co_worker,
            role=15,
            workflow_roles=[ProjectMember.WorkflowRole.CO_WORKER],
        )
        ProjectMember.objects.create(
            project=project,
            member=second_co_worker,
            role=15,
            workflow_roles=[ProjectMember.WorkflowRole.CO_WORKER],
        )
        ProjectMember.objects.create(project=project, member=creator, role=20)

        state = State.objects.create(
            name="Todo",
            color="#60646C",
            group="unstarted",
            default=True,
            project=project,
            workspace=workspace,
        )
        issue = Issue.objects.create(
            name="Workflow issue",
            project=project,
            state=state,
            created_by=creator,
        )

        api_client.force_authenticate(user=creator)

        response = api_client.patch(
            f"/api/workspaces/{workspace.slug}/projects/{project.id}/issues/{issue.id}/workflow-members/",
            {"co_worker_ids": [str(co_worker.id), str(second_co_worker.id)]},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert set(
            IssueSubscriber.objects.filter(issue=issue, project=project).values_list("subscriber_id", flat=True)
        ) == {co_worker.id, second_co_worker.id}

        response = api_client.patch(
            f"/api/workspaces/{workspace.slug}/projects/{project.id}/issues/{issue.id}/workflow-members/",
            {"co_worker_ids": [str(co_worker.id), str(second_co_worker.id)]},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert (
            IssueSubscriber.objects.filter(
                issue=issue,
                project=project,
            ).count()
            == 2
        )

    @pytest.mark.django_db
    def test_assigned_profile_view_includes_assignee_and_approver_issues(self, api_client):
        target_user = UserFactory(email="target-user@plane.so", username="target-user")
        creator = UserFactory(email="creator@plane.so", username="creator")

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
            workspace=workspace,
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
        target_user = UserFactory(email="target-priority@plane.so", username="target-priority")
        creator = UserFactory(email="priority-creator@plane.so", username="priority-creator")

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
            workspace=workspace,
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
        target_user = UserFactory(email="target-creator@plane.so", username="target-creator")
        other_user = UserFactory(email="other-user@plane.so", username="other-user")

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
            workspace=workspace,
        )

        created_issue = Issue.objects.create(
            name="Created by target",
            project=project,
            state=state,
            created_by=target_user,
        )
        created_issue.created_by = target_user
        created_issue.save(disable_auto_set_user=True)
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

    @pytest.mark.django_db
    def test_subscribed_profile_view_only_includes_subscribed_issues(self, api_client):
        target_user = UserFactory(email="target-subscriber@plane.so", username="target-subscriber")
        other_user = UserFactory(email="subscriber-other-user@plane.so", username="subscriber-other-user")

        workspace = Workspace.objects.create(name="Subscribed Workspace", slug="subscribed-workspace", owner=other_user)
        WorkspaceMember.objects.create(workspace=workspace, member=target_user, role=15)
        WorkspaceMember.objects.create(workspace=workspace, member=other_user, role=15)

        project = Project.objects.create(
            name="Subscribed Project",
            identifier="SUBS",
            workspace=workspace,
            created_by=other_user,
            updated_by=other_user,
        )
        ProjectMember.objects.create(project=project, member=target_user, role=15)
        ProjectMember.objects.create(project=project, member=other_user, role=15)

        state = State.objects.create(
            name="Todo",
            color="#60646C",
            group="unstarted",
            default=True,
            project=project,
            workspace=workspace,
        )

        subscribed_issue = Issue.objects.create(
            name="Subscribed by target",
            project=project,
            state=state,
            created_by=other_user,
        )
        IssueSubscriber.objects.create(issue=subscribed_issue, subscriber=target_user, project=project)

        assigned_but_not_subscribed = Issue.objects.create(
            name="Assigned but not subscribed",
            project=project,
            state=state,
            created_by=other_user,
        )
        IssueAssignee.objects.create(issue=assigned_but_not_subscribed, assignee=target_user, project=project)

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
                "subscriber": str(target_user.id),
            },
        )

        assert response.status_code == status.HTTP_200_OK
        returned_issue_ids = {
            str(issue["id"])
            for group in response.data["results"].values()
            for issue in group["results"]
        }

        assert str(subscribed_issue.id) in returned_issue_ids
        assert str(assigned_but_not_subscribed.id) not in returned_issue_ids
        assert response.data["total_count"] == 1

    @pytest.mark.django_db
    def test_created_and_subscribed_profile_views_match_across_grouping_modes(self, api_client):
        target_user = UserFactory(email="target-layout@plane.so", username="target-layout")
        other_user = UserFactory(email="layout-other-user@plane.so", username="layout-other-user")

        workspace = Workspace.objects.create(name="Layout Workspace", slug="layout-workspace", owner=target_user)
        WorkspaceMember.objects.create(workspace=workspace, member=target_user, role=15)
        WorkspaceMember.objects.create(workspace=workspace, member=other_user, role=15)

        project = Project.objects.create(
            name="Layout Project",
            identifier="LAYT",
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
            workspace=workspace,
        )
        created_issue = Issue.objects.create(
            name="Created layout issue",
            project=project,
            state=state,
            priority="none",
            created_by=target_user,
        )
        created_issue.created_by = target_user
        created_issue.save(disable_auto_set_user=True)
        subscribed_issue = Issue.objects.create(
            name="Subscribed layout issue",
            project=project,
            state=state,
            priority="high",
            created_by=other_user,
        )
        IssueSubscriber.objects.create(issue=subscribed_issue, subscriber=target_user, project=project)
        unrelated_issue = Issue.objects.create(
            name="Unrelated layout issue",
            project=project,
            state=state,
            priority="medium",
            created_by=other_user,
        )
        IssueAssignee.objects.create(issue=unrelated_issue, assignee=target_user, project=project)

        api_client.force_authenticate(user=target_user)

        def fetch_ids(view_param, group_by):
            response = api_client.get(
                f"/api/workspaces/{workspace.slug}/user-issues/{target_user.id}/",
                {
                    "group_by": group_by,
                    "order_by": "sort_order",
                    "sub_issue": "false",
                    "filters": "{}",
                    "layout": "list",
                    "cursor": "50:0:0",
                    "per_page": "50",
                    view_param: str(target_user.id),
                },
            )
            assert response.status_code == status.HTTP_200_OK
            return {
                "total_count": response.data["total_count"],
                "ids": {
                    str(issue["id"])
                    for group in response.data["results"].values()
                    for issue in group["results"]
                },
            }

        created_by_state = fetch_ids("created_by", "state_id")
        created_by_priority = fetch_ids("created_by", "priority")
        subscribed_by_state = fetch_ids("subscriber", "state_id")
        subscribed_by_priority = fetch_ids("subscriber", "priority")

        assert created_by_state == created_by_priority == {"total_count": 1, "ids": {str(created_issue.id)}}
        assert subscribed_by_state == subscribed_by_priority == {
            "total_count": 1,
            "ids": {str(subscribed_issue.id)},
        }

/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useMemo, useState } from "react";
import { observer } from "mobx-react";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { MembersPropertyIcon, UserCirclePropertyIcon } from "@plane/propel/icons";
// components
import { SidebarPropertyListItem } from "@/components/common/layout/sidebar/property-list-item";
import { MemberDropdown } from "@/components/dropdowns/member/dropdown";
import { useMember } from "@/hooks/store/use-member";
// services
import {
  IssueWorkflowMemberService,
  type TIssueWorkflowMembersResponse,
} from "@/services/issue/issue_workflow_member.service";

type Props = {
  workspaceSlug: string;
  projectId: string;
  issueId: string;
  assigneeIds?: string[];
  disabled: boolean;
};

type TWorkflowMemberState = {
  approverId: string | null;
  coWorkerIds: string[];
};

const getWorkflowMemberState = (response: TIssueWorkflowMembersResponse): TWorkflowMemberState => ({
  approverId: response.approver?.member ?? null,
  coWorkerIds: response.co_workers.map((coWorker) => coWorker.member),
});

const showUpdateError = () =>
  setToast({
    type: TOAST_TYPE.ERROR,
    title: "Workflow members not updated",
    message: "Unable to update Approver or Co-worker for this work item.",
  });

export const WorkflowMembersProperty = observer(function WorkflowMembersProperty(props: Props) {
  const { workspaceSlug, projectId, issueId, assigneeIds = [], disabled } = props;
  const workflowMemberService = useMemo(() => new IssueWorkflowMemberService(), []);
  const {
    project: { fetchProjectMembers, getProjectMemberIdsByWorkflowRole },
  } = useMember();
  // state
  const [isLoading, setIsLoading] = useState(false);
  const [members, setMembers] = useState<TWorkflowMemberState>({
    approverId: null,
    coWorkerIds: [],
  });
  const excludedAssigneeIds = useMemo(() => new Set(assigneeIds), [assigneeIds]);
  const approverMemberIds = getProjectMemberIdsByWorkflowRole(projectId, "approver", assigneeIds) ?? [];
  const coWorkerMemberIds =
    getProjectMemberIdsByWorkflowRole(
      projectId,
      "co_worker",
      members.approverId ? [...assigneeIds, members.approverId] : assigneeIds
    ) ?? [];

  useEffect(() => {
    let isMounted = true;
    setIsLoading(true);

    const fetchWorkflowMembers = async () => {
      try {
        const response = await workflowMemberService.retrieve(workspaceSlug, projectId, issueId);
        if (!isMounted) return;
        setMembers(getWorkflowMemberState(response));
      } catch {
        if (!isMounted) return;
        showUpdateError();
      } finally {
        if (isMounted) setIsLoading(false);
      }
    };

    fetchWorkflowMembers();

    return () => {
      isMounted = false;
    };
  }, [issueId, projectId, workflowMemberService, workspaceSlug]);

  useEffect(() => {
    fetchProjectMembers(workspaceSlug, projectId);
  }, [fetchProjectMembers, projectId, workspaceSlug]);

  const handleApproverChange = async (approverId: string | null) => {
    if (approverId && excludedAssigneeIds.has(approverId)) return;
    const nextApproverId = approverId === members.approverId ? null : approverId;
    const previousMembers = members;
    const nextMembers = {
      approverId: nextApproverId,
      coWorkerIds: nextApproverId
        ? members.coWorkerIds.filter((memberId) => memberId !== nextApproverId)
        : members.coWorkerIds,
    };
    setMembers(nextMembers);

    try {
      const response = await workflowMemberService.update(workspaceSlug, projectId, issueId, {
        approver_id: nextApproverId,
        co_worker_ids: nextMembers.coWorkerIds,
      });
      setMembers(getWorkflowMemberState(response));
    } catch {
      setMembers(previousMembers);
      showUpdateError();
    }
  };

  const handleCoWorkersChange = async (coWorkerIds: string[]) => {
    const previousMembers = members;
    const nextMembers = {
      ...members,
      coWorkerIds: coWorkerIds.filter(
        (memberId) => memberId !== members.approverId && !excludedAssigneeIds.has(memberId)
      ),
    };
    setMembers(nextMembers);

    try {
      const response = await workflowMemberService.update(workspaceSlug, projectId, issueId, {
        co_worker_ids: nextMembers.coWorkerIds,
      });
      setMembers(getWorkflowMemberState(response));
    } catch {
      setMembers(previousMembers);
      showUpdateError();
    }
  };

  return (
    <>
      <SidebarPropertyListItem icon={UserCirclePropertyIcon} label="Approver">
        <MemberDropdown
          value={members.approverId}
          onChange={handleApproverChange}
          disabled={disabled || isLoading}
          projectId={projectId}
          memberIds={approverMemberIds}
          placeholder="Select Approver"
          multiple={false}
          buttonVariant="transparent-with-text"
          className="group w-full grow"
          buttonContainerClassName="w-full text-left h-7.5"
          buttonClassName={`text-body-xs-regular justify-between ${members.approverId ? "" : "text-placeholder"}`}
          hideIcon={!members.approverId}
          dropdownArrow
          dropdownArrowClassName="h-3.5 w-3.5 hidden group-hover:inline"
          showUserDetails
        />
      </SidebarPropertyListItem>
      <SidebarPropertyListItem icon={MembersPropertyIcon} label="Co-worker">
        <MemberDropdown
          value={members.coWorkerIds}
          onChange={handleCoWorkersChange}
          disabled={disabled || isLoading}
          projectId={projectId}
          memberIds={coWorkerMemberIds}
          placeholder="Select Co-worker"
          multiple
          buttonVariant={members.coWorkerIds.length > 1 ? "transparent-without-text" : "transparent-with-text"}
          className="group w-full grow"
          buttonContainerClassName="w-full text-left h-7.5"
          buttonClassName={`text-body-xs-regular justify-between ${members.coWorkerIds.length > 0 ? "" : "text-placeholder"}`}
          hideIcon={members.coWorkerIds.length === 0}
          dropdownArrow
          dropdownArrowClassName="h-3.5 w-3.5 hidden group-hover:inline"
          showUserDetails
        />
      </SidebarPropertyListItem>
    </>
  );
});

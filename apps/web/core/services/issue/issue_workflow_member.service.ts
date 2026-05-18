/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { API_BASE_URL } from "@plane/constants";
import { APIService } from "@/services/api.service";

export type TIssueWorkflowMemberRole = "approver" | "co_worker";

export type TIssueWorkflowMember = {
  id: string;
  issue_id: string;
  project_id: string;
  workspace_id: string;
  member: string;
  member_detail?: {
    id: string;
    display_name: string;
    email?: string;
    avatar_url?: string | null;
  };
  role_type: TIssueWorkflowMemberRole;
};

export type TIssueWorkflowMembersResponse = {
  approver: TIssueWorkflowMember | null;
  co_workers: TIssueWorkflowMember[];
};

export type TIssueWorkflowMembersPayload = {
  approver_id?: string | null;
  co_worker_ids?: string[];
};

export class IssueWorkflowMemberService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  async retrieve(
    workspaceSlug: string,
    projectId: string,
    issueId: string
  ): Promise<TIssueWorkflowMembersResponse> {
    return this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/issues/${issueId}/workflow-members/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async update(
    workspaceSlug: string,
    projectId: string,
    issueId: string,
    data: TIssueWorkflowMembersPayload
  ): Promise<TIssueWorkflowMembersResponse> {
    return this.patch(`/api/workspaces/${workspaceSlug}/projects/${projectId}/issues/${issueId}/workflow-members/`, data)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }
}

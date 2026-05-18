/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { API_BASE_URL } from "@plane/constants";
import { APIService } from "@/services/api.service";

export type TStateTransitionAllowedRole = "approver" | "co_worker" | "assignee" | "creator";

export type TStateTransitionRule = {
  id: string;
  project_id: string;
  workspace_id: string;
  from_state: string;
  to_state: string;
  allowed_roles: TStateTransitionAllowedRole[];
  requires_approval: boolean;
  notify_enabled: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type TStateTransitionRulePayload = {
  from_state?: string;
  to_state?: string;
  allowed_roles?: TStateTransitionAllowedRole[];
  requires_approval?: boolean;
  notify_enabled?: boolean;
  is_active?: boolean;
};

export class StateTransitionRuleService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  async list(workspaceSlug: string, projectId: string): Promise<TStateTransitionRule[]> {
    return this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/state-transition-rules/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async create(
    workspaceSlug: string,
    projectId: string,
    data: TStateTransitionRulePayload
  ): Promise<TStateTransitionRule> {
    return this.post(`/api/workspaces/${workspaceSlug}/projects/${projectId}/state-transition-rules/`, data)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async update(
    workspaceSlug: string,
    projectId: string,
    ruleId: string,
    data: TStateTransitionRulePayload
  ): Promise<TStateTransitionRule> {
    return this.patch(`/api/workspaces/${workspaceSlug}/projects/${projectId}/state-transition-rules/${ruleId}/`, data)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }
}

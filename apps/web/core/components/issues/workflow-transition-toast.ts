/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { TOAST_TYPE, setToast } from "@plane/propel/toast";

type TWorkflowTransitionResponse = {
  approval_required?: boolean;
  missing_approver?: boolean;
  transition_restricted?: boolean;
  missing_transition_rule?: boolean;
  disabled_transition_rule?: boolean;
  detail?: string;
  error?: string;
};

type TWorkflowTransitionError = TWorkflowTransitionResponse & {
  data?: TWorkflowTransitionResponse;
  response?: {
    data?: TWorkflowTransitionResponse;
  };
};

const getWorkflowTransitionPayload = (value: unknown): TWorkflowTransitionResponse | undefined => {
  if (!value || typeof value !== "object") return undefined;

  const error = value as TWorkflowTransitionError;
  return error.response?.data ?? error.data ?? error;
};

const WORKFLOW_PERMISSION_LIMIT_MESSAGE = "您的操作超出权限限制范围";

export const showWorkflowTransitionNotice = (response: unknown): boolean => {
  const payload = getWorkflowTransitionPayload(response);
  if (!payload) return false;

  if (payload.approval_required) {
    setToast({
      type: TOAST_TYPE.WARNING,
      title: payload.missing_approver ? "需要指定 Approver" : "需要审批",
      message: payload.missing_approver
        ? "该状态流转需要审批，请先在工作项属性中指定 Approver。"
        : payload.detail || "审批请求已创建，当前状态暂未切换。",
    });
    return true;
  }

  if (payload.transition_restricted || payload.missing_transition_rule || payload.disabled_transition_rule) {
    setToast({
      type: TOAST_TYPE.ERROR,
      title: "状态未切换",
      message: WORKFLOW_PERMISSION_LIMIT_MESSAGE,
    });
    return true;
  }

  return false;
};

export const showWorkflowTransitionError = (error: unknown): boolean => {
  if (showWorkflowTransitionNotice(error)) return true;

  const payload = getWorkflowTransitionPayload(error);
  if (payload?.error) {
    setToast({
      type: TOAST_TYPE.ERROR,
      title: "状态未切换",
      message: payload.error,
    });
    return true;
  }

  return false;
};

/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useMemo, useState } from "react";
import { observer } from "mobx-react";
import { Check, Loader2, Mail, ShieldCheck, UserCheck, Users } from "lucide-react";
import { EUserPermissions, EUserPermissionsLevel } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { Button, Spinner } from "@plane/ui";
import type { IState } from "@plane/types";
// components
import { NotAuthorizedView } from "@/components/auth-screens/not-authorized-view";
import { PageHead } from "@/components/core/page-title";
import { SettingsContentWrapper } from "@/components/settings/content-wrapper";
import { SettingsHeading } from "@/components/settings/heading";
// hooks
import { useProject } from "@/hooks/store/use-project";
import { useProjectState } from "@/hooks/store/use-project-state";
import { useUserPermissions } from "@/hooks/store/user";
// services
import {
  StateTransitionRuleService,
  type TStateTransitionAllowedRole,
  type TStateTransitionRule,
  type TStateTransitionRulePayload,
} from "@/services/project/state-transition-rule.service";
// local imports
import type { Route } from "./+types/page";
import { WorkflowsProjectSettingsHeader } from "./header";

const ROLE_OPTIONS: {
  key: TStateTransitionAllowedRole;
  label: string;
  icon: typeof UserCheck;
}[] = [
  { key: "approver", label: "Approver", icon: ShieldCheck },
  { key: "co_worker", label: "Co-worker", icon: Users },
  { key: "assignee", label: "Assignee", icon: UserCheck },
  { key: "creator", label: "Creator", icon: UserCheck },
];

const transitionKey = (fromStateId: string, toStateId: string) => `${fromStateId}:${toStateId}`;

const showWorkflowError = () =>
  setToast({
    type: TOAST_TYPE.ERROR,
    title: "Workflow rule not updated",
    message: "Unable to save this workflow transition rule.",
  });

type TWorkflowMatrixCellProps = {
  disabled: boolean;
  fromState: IState;
  onUpsert: (fromStateId: string, toStateId: string, payload: TStateTransitionRulePayload) => Promise<void>;
  rule: TStateTransitionRule | undefined;
  toState: IState;
};

const WorkflowMatrixCell = observer(function WorkflowMatrixCell(props: TWorkflowMatrixCellProps) {
  const { disabled, fromState, onUpsert, rule, toState } = props;
  const [isSaving, setIsSaving] = useState(false);

  const save = async (payload: TStateTransitionRulePayload) => {
    setIsSaving(true);
    try {
      await onUpsert(fromState.id, toState.id, payload);
    } catch {
      showWorkflowError();
    } finally {
      setIsSaving(false);
    }
  };

  if (fromState.id === toState.id) {
    return <div className="text-sm flex h-full min-h-28 items-center justify-center text-placeholder">-</div>;
  }

  if (!rule) {
    return (
      <div className="flex min-h-28 items-center justify-center">
        <Button
          variant="neutral-primary"
          size="sm"
          disabled={disabled || isSaving}
          loading={isSaving}
          onClick={() =>
            save({
              allowed_roles: ["approver"],
              is_active: true,
              notify_enabled: true,
              requires_approval: true,
            })
          }
        >
          配置
        </Button>
      </div>
    );
  }

  const allowedRoles = rule.allowed_roles ?? [];

  const handleRoleToggle = (role: TStateTransitionAllowedRole) => {
    const nextRoles = allowedRoles.includes(role)
      ? allowedRoles.filter((allowedRole) => allowedRole !== role)
      : [...allowedRoles, role];
    save({ allowed_roles: nextRoles });
  };

  return (
    <div className="text-xs min-h-28 space-y-2 p-2">
      <div className="flex items-center justify-between gap-2">
        <label className="flex items-center gap-1.5 text-secondary">
          <input
            type="checkbox"
            className="size-3.5"
            disabled={disabled || isSaving}
            checked={rule.is_active}
            onChange={(event) => save({ is_active: event.currentTarget.checked })}
          />
          启用
        </label>
        {isSaving && <Loader2 className="size-3.5 animate-spin text-secondary" />}
      </div>

      <div className="flex flex-wrap gap-1">
        {ROLE_OPTIONS.map((roleOption) => {
          const Icon = roleOption.icon;
          const isSelected = allowedRoles.includes(roleOption.key);
          return (
            <button
              key={roleOption.key}
              type="button"
              disabled={disabled || isSaving}
              onClick={() => handleRoleToggle(roleOption.key)}
              className={`flex items-center gap-1 rounded border px-1.5 py-1 text-left ${
                isSelected
                  ? "border-custom-primary-100 bg-custom-primary-100/10 text-custom-primary-100"
                  : "border-subtle-1 text-secondary hover:bg-surface-2"
              }`}
            >
              <Icon className="size-3" />
              <span>{roleOption.label}</span>
            </button>
          );
        })}
        {allowedRoles.length === 0 && (
          <span className="rounded bg-surface-2 px-1.5 py-1 text-placeholder">Admin only</span>
        )}
      </div>

      <div className="grid grid-cols-2 gap-2 text-secondary">
        <label className="flex items-center gap-1.5">
          <input
            type="checkbox"
            className="size-3.5"
            disabled={disabled || isSaving}
            checked={rule.requires_approval}
            onChange={(event) => save({ requires_approval: event.currentTarget.checked })}
          />
          <Check className="size-3" />
          审批
        </label>
        <label className="flex items-center gap-1.5">
          <input
            type="checkbox"
            className="size-3.5"
            disabled={disabled || isSaving}
            checked={rule.notify_enabled}
            onChange={(event) => save({ notify_enabled: event.currentTarget.checked })}
          />
          <Mail className="size-3" />
          邮件
        </label>
      </div>
    </div>
  );
});

function WorkflowsSettingsPage({ params }: Route.ComponentProps) {
  const { workspaceSlug, projectId } = params;
  const { t } = useTranslation();
  const { currentProjectDetails } = useProject();
  const { fetchProjectStates, getProjectStates } = useProjectState();
  const { workspaceUserInfo, allowPermissions } = useUserPermissions();
  const transitionRuleService = useMemo(() => new StateTransitionRuleService(), []);
  // states
  const [rules, setRules] = useState<TStateTransitionRule[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const states = getProjectStates(projectId) ?? [];
  const rulesByTransition = useMemo(
    () => new Map(rules.map((rule) => [transitionKey(rule.from_state, rule.to_state), rule])),
    [rules]
  );

  const canManageWorkflows = allowPermissions([EUserPermissions.ADMIN], EUserPermissionsLevel.PROJECT);
  const pageTitle = currentProjectDetails?.name ? `${currentProjectDetails.name} - Workflows` : undefined;

  useEffect(() => {
    let isMounted = true;
    setIsLoading(true);

    const fetchData = async () => {
      try {
        await fetchProjectStates(workspaceSlug, projectId);
        const response = await transitionRuleService.list(workspaceSlug, projectId);
        if (!isMounted) return;
        setRules(response);
      } catch {
        if (isMounted) showWorkflowError();
      } finally {
        if (isMounted) setIsLoading(false);
      }
    };

    fetchData();

    return () => {
      isMounted = false;
    };
  }, [fetchProjectStates, projectId, transitionRuleService, workspaceSlug]);

  const upsertRule = async (fromStateId: string, toStateId: string, payload: TStateTransitionRulePayload) => {
    const currentRule = rulesByTransition.get(transitionKey(fromStateId, toStateId));
    const response = currentRule
      ? await transitionRuleService.update(workspaceSlug, projectId, currentRule.id, payload)
      : await transitionRuleService.create(workspaceSlug, projectId, {
          allowed_roles: ["approver"],
          from_state: fromStateId,
          is_active: true,
          notify_enabled: true,
          requires_approval: true,
          to_state: toStateId,
          ...payload,
        });

    setRules((currentRules) => {
      const filteredRules = currentRules.filter((rule) => rule.id !== response.id);
      return [...filteredRules, response];
    });
  };

  if (workspaceUserInfo && !canManageWorkflows) {
    return <NotAuthorizedView section="settings" isProjectView className="h-auto" />;
  }

  return (
    <SettingsContentWrapper header={<WorkflowsProjectSettingsHeader />}>
      <PageHead title={pageTitle} />
      <div className="w-full">
        <SettingsHeading title="流程" description="用状态流转矩阵配置每条流程允许的角色、审批要求和邮件通知。" />

        <div className="mt-6 rounded border border-subtle-1">
          {isLoading ? (
            <div className="flex h-48 items-center justify-center">
              <Spinner />
            </div>
          ) : states.length === 0 ? (
            <div className="text-sm p-6 text-secondary">请先在“{t("common.states")}”中创建项目状态。</div>
          ) : (
            <div className="overflow-auto">
              <table className="min-w-full border-collapse text-left">
                <thead>
                  <tr className="bg-surface-2">
                    <th className="text-xs sticky left-0 z-10 min-w-36 border-r border-subtle-1 bg-surface-2 p-3 font-medium text-secondary">
                      From / To
                    </th>
                    {states.map((state) => (
                      <th
                        key={state.id}
                        className="text-xs min-w-64 border-r border-subtle-1 p-3 font-medium text-secondary"
                      >
                        <div className="flex items-center gap-2">
                          <span className="size-2 rounded-full" style={{ backgroundColor: state.color }} />
                          <span className="truncate">{state.name}</span>
                        </div>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {states.map((fromState) => (
                    <tr key={fromState.id} className="border-t border-subtle-1">
                      <th className="text-xs sticky left-0 z-10 min-w-36 border-r border-subtle-1 bg-surface-1 p-3 font-medium text-secondary">
                        <div className="flex items-center gap-2">
                          <span className="size-2 rounded-full" style={{ backgroundColor: fromState.color }} />
                          <span className="truncate">{fromState.name}</span>
                        </div>
                      </th>
                      {states.map((toState) => (
                        <td key={toState.id} className="min-w-64 border-r border-subtle-1 align-top">
                          <WorkflowMatrixCell
                            disabled={!canManageWorkflows}
                            fromState={fromState}
                            onUpsert={upsertRule}
                            rule={rulesByTransition.get(transitionKey(fromState.id, toState.id))}
                            toState={toState}
                          />
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </SettingsContentWrapper>
  );
}

export default observer(WorkflowsSettingsPage);

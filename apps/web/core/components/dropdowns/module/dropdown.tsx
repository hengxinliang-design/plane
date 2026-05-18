/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, type ReactNode } from "react";
import { observer } from "mobx-react";
import { useParams } from "next/navigation";
// hooks
import { useModule } from "@/hooks/store/use-module";
// types
import type { TDropdownProps } from "../types";
// local imports
import { ModuleDropdownBase } from "./base";

type TModuleDropdownProps = TDropdownProps & {
  button?: ReactNode;
  dropdownArrow?: boolean;
  dropdownArrowClassName?: string;
  projectId: string | undefined;
  showCount?: boolean;
  onClose?: () => void;
  renderByDefault?: boolean;
  itemClassName?: string;
} & (
    | {
        multiple: false;
        onChange: (val: string | null) => void;
        value: string | null;
      }
    | {
        multiple: true;
        onChange: (val: string[]) => void;
        value: string[] | null;
      }
  );

export const ModuleDropdown = observer(function ModuleDropdown(props: TModuleDropdownProps) {
  const { projectId } = props;
  // router
  const { workspaceSlug } = useParams();
  // store hooks
  const { getModuleById, getProjectModuleIds, fetchModules } = useModule();
  // derived values
  const moduleIds = projectId ? getProjectModuleIds(projectId) : [];
  const selectedModuleIds = Array.isArray(props.value) ? props.value : props.value ? [props.value] : [];
  const hasMissingSelectedModuleDetails = selectedModuleIds.some((moduleId) => !getModuleById(moduleId));

  const onDropdownOpen = () => {
    if (!moduleIds && projectId && workspaceSlug) fetchModules(workspaceSlug.toString(), projectId);
  };

  useEffect(() => {
    if (!projectId || !workspaceSlug || !hasMissingSelectedModuleDetails) return;

    fetchModules(workspaceSlug.toString(), projectId);
  }, [fetchModules, hasMissingSelectedModuleDetails, projectId, workspaceSlug]);

  return (
    <ModuleDropdownBase
      {...props}
      getModuleById={getModuleById}
      moduleIds={moduleIds ?? []}
      onDropdownOpen={onDropdownOpen}
    />
  );
});

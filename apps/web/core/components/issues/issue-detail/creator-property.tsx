/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
// constants
import { EUserPermissions, EUserPermissionsLevel } from "@plane/constants";
// components
import { ButtonAvatars } from "@/components/dropdowns/member/avatar";
import { MemberDropdown } from "@/components/dropdowns/member/dropdown";
// hooks
import { useMember } from "@/hooks/store/use-member";
import { useUserPermissions } from "@/hooks/store/user";
// local imports
import type { TIssueOperations } from "./root";

type Props = {
  workspaceSlug: string;
  projectId: string;
  issueId: string;
  createdBy: string | null | undefined;
  disabled?: boolean;
  issueOperations: TIssueOperations;
  textClassName?: string;
};

export const IssueCreatorProperty = observer(function IssueCreatorProperty(props: Props) {
  const { workspaceSlug, projectId, issueId, createdBy, disabled = false, issueOperations, textClassName } = props;
  const { getUserDetails } = useMember();
  const { allowPermissions } = useUserPermissions();

  const createdByDetails = createdBy ? getUserDetails(createdBy) : undefined;
  const canUpdateCreator =
    allowPermissions([EUserPermissions.ADMIN], EUserPermissionsLevel.PROJECT, workspaceSlug, projectId) ||
    allowPermissions([EUserPermissions.ADMIN], EUserPermissionsLevel.WORKSPACE, workspaceSlug);
  const isIntakeCreator = createdByDetails?.display_name.includes("-intake");

  if (!canUpdateCreator || isIntakeCreator) {
    if (!createdByDetails) return null;
    return (
      <div className="flex gap-2 px-2">
        <ButtonAvatars showTooltip userIds={isIntakeCreator ? null : createdByDetails.id} />
        <span className={textClassName ?? "grow truncate text-body-xs-regular leading-5"}>
          {isIntakeCreator ? "Plane" : createdByDetails.display_name}
        </span>
      </div>
    );
  }

  return (
    <MemberDropdown
      value={createdBy ?? null}
      onChange={(val) => {
        if (val && val !== createdBy) issueOperations.update(workspaceSlug, projectId, issueId, { created_by: val });
      }}
      disabled={disabled}
      projectId={projectId}
      placeholder="Select creator"
      multiple={false}
      showUserDetails
      buttonVariant="transparent-with-text"
      className="group h-7.5 w-full grow"
      buttonContainerClassName="w-full text-left h-7.5"
      buttonClassName={`justify-between px-2 py-0.5 ${textClassName ?? "text-body-xs-regular"}`}
      dropdownArrow
      dropdownArrowClassName="h-3.5 w-3.5 hidden group-hover:inline"
    />
  );
});

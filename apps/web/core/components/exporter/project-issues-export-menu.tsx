/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useCallback, useState } from "react";
import { Download, Ellipsis } from "lucide-react";
import { EUserPermissions, EUserPermissionsLevel } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import { IconButton } from "@plane/propel/icon-button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { CustomMenu } from "@plane/ui";
import { useUserPermissions } from "@/hooks/store/user";
import { ProjectExportService } from "@/services/project/project-export.service";

type Props = {
  workspaceSlug: string;
  projectId: string;
};

const projectExportService = new ProjectExportService();

export function ProjectIssuesExportMenu({ workspaceSlug, projectId }: Props) {
  const { t } = useTranslation();
  const { allowPermissions } = useUserPermissions();
  const [isExporting, setIsExporting] = useState(false);

  const canUserExport = allowPermissions(
    [EUserPermissions.ADMIN, EUserPermissions.MEMBER],
    EUserPermissionsLevel.WORKSPACE
  );

  const handleCsvExport = useCallback(async () => {
    if (!workspaceSlug || !projectId || isExporting) return;

    setIsExporting(true);
    try {
      await projectExportService.csvExport(workspaceSlug, {
        provider: "csv",
        project: [projectId],
        multiple: false,
      });
      setToast({
        type: TOAST_TYPE.SUCCESS,
        title: t("workspace_settings.settings.exports.modal.toasts.success.title"),
        message: t("workspace_settings.settings.exports.modal.toasts.success.message", { entity: "CSV" }),
      });
    } catch (_error) {
      setToast({
        type: TOAST_TYPE.ERROR,
        title: t("error"),
        message: t("workspace_settings.settings.exports.modal.toasts.error.message"),
      });
    } finally {
      setIsExporting(false);
    }
  }, [isExporting, projectId, t, workspaceSlug]);

  if (!canUserExport) return null;

  return (
    <CustomMenu
      ellipsis
      placement="bottom-end"
      customButton={<IconButton size="lg" variant="tertiary" icon={Ellipsis} aria-label={t("more")} />}
    >
      <CustomMenu.MenuItem
        onClick={() => void handleCsvExport()}
        className="flex items-center gap-2"
        disabled={isExporting}
      >
        <Download className="size-3.5" />
        <span>{t("exporter.csv.download")}</span>
      </CustomMenu.MenuItem>
    </CustomMenu>
  );
}

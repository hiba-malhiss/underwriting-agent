import { SparklesIcon } from "lucide-react";
import { toast } from "sonner";
import type { StoredDocument } from "@/api/types";
import { useDeleteDocument, useDocumentsQuery, useUploadDocument } from "@/api/documents";
import type { Parameter, Rule } from "@/api/rules";
import { useCurrentRulebook, useProposeRules, useSaveRuleVersion } from "@/api/rules";
import { Button } from "@/components/ui/button";
import { DocumentList } from "@/components/documents/DocumentList/DocumentList";
import { DocumentUpload } from "@/components/documents/DocumentUpload/DocumentUpload";
import { CurrentRules } from "@/components/rules/CurrentRules/CurrentRules";
import { ProposalReview } from "@/components/rules/ProposalReview/ProposalReview";
import { REQUIREMENT_FILE_TYPES } from "@/config";

// The underwriting guidelines, and the rules approved from them
export function RequirementsPage() {
  const documents = useDocumentsQuery("requirement");
  const upload = useUploadDocument("requirement");
  const remove = useDeleteDocument("requirement");

  const current = useCurrentRulebook();
  const propose = useProposeRules();
  const save = useSaveRuleVersion();

  const suggestRules = async (document: StoredDocument) => {
    try {
      const proposal = await propose.mutateAsync(document.name);
      toast.success(`${proposal.rules.length} rules suggested from ${document.filename}`);
    } catch (e) {
      toast.error(`${document.filename}: ${(e as Error).message}`);
    }
  };

  const saveApproved = async (rules: Rule[], parameters: Parameter[]) => {
    if (!propose.data) return;
    try {
      const saved = await save.mutateAsync({
        based_on_version: propose.data.based_on_version,
        parameters,
        rules,
        note: `From ${propose.data.document}`,
      });
      toast.success(`Saved as version ${saved.version}`);
      propose.reset(); // close the review
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Requirements</h1>
        <p className="text-sm text-muted-foreground">
          Underwriting guidelines. Uploading a file with the same name replaces the old version.
        </p>
      </div>
      <DocumentUpload
        title="Upload guidelines"
        description="Eligibility rules, required documents, medical criteria."
        fileTypes={REQUIREMENT_FILE_TYPES}
        uploading={upload.isPending}
        onUpload={upload.mutateAsync}
      />
      <DocumentList
        documents={documents.data ?? []}
        loading={documents.isPending}
        error={documents.error?.message ?? null}
        deleting={remove.isPending ? remove.variables : null}
        onDelete={remove.mutateAsync}
        renderActions={(document) => (
          <Button
            variant="outline"
            size="sm"
            disabled={propose.isPending}
            onClick={() => void suggestRules(document)}
          >
            <SparklesIcon />
            {propose.isPending && propose.variables === document.name
              ? "Reading… (up to a minute)"
              : "Suggest rules"}
          </Button>
        )}
      />
      {propose.data && (
        // key: a new proposal starts with fresh checkboxes
        <ProposalReview
          key={`${propose.data.document}-${propose.submittedAt}`}
          proposal={propose.data}
          saving={save.isPending}
          onSave={saveApproved}
          onCancel={() => propose.reset()}
        />
      )}
      <CurrentRules
        current={current.data}
        loading={current.isPending}
        error={current.error?.message ?? null}
      />
    </div>
  );
}

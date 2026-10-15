import { notFound } from "next/navigation";
import { BackendError, backendGet } from "@/lib/server-api";
import type { Catalog, Patient } from "@/lib/types";
import LabForm from "./LabForm";

export const dynamic = "force-dynamic";

export default async function LabEntryPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  let patient: Patient;
  try {
    patient = await backendGet<Patient>(`/patients/${id}`);
  } catch (e) {
    if (e instanceof BackendError && (e.status === 404 || e.status === 422)) notFound();
    throw e;
  }
  const catalog = await backendGet<Catalog>("/bioage/biomarkers");
  return (
    <>
      <h1>手工录入指标 · {patient.pseudonym}</h1>
      <LabForm patient={patient} catalog={catalog} />
    </>
  );
}

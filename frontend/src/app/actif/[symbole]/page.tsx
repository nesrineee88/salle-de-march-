import FicheActif from "@/components/FicheActif";

export default async function Page({ params }: { params: Promise<{ symbole: string }> }) {
  const { symbole } = await params;
  return <FicheActif symbole={decodeURIComponent(symbole)} />;
}

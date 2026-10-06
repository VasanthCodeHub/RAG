import { useState } from "react";
import { Bot, FileSearch, Flag, ShieldCheck } from "lucide-react";
import { PageHero, Tabs, TabPanel } from "../components";
import { DocumentAgentTab } from "../components/agents/DocumentAgentTab";
import { ClaimsRaceTab } from "../components/agents/ClaimsRaceTab";
import { SafetyTab } from "../components/agents/SafetyTab";

export default function AgentsPage() {
  const [tab, setTab] = useState("document");
  return (
    <>
      <PageHero icon={<Bot size={28} />} title="Agents">
        Single tool-calling agents, a budgeted agent-vs-workflow race, and safety evaluation: trajectories and prompt injection.
      </PageHero>
      <Tabs
        active={tab}
        onChange={setTab}
        tabs={[
          { id: "document", label: "Document agent", icon: <FileSearch size={15} /> },
          { id: "race", label: "Claims race", icon: <Flag size={15} /> },
          { id: "safety", label: "Safety", icon: <ShieldCheck size={15} /> },
        ]}
      />
      <TabPanel id={tab}>
        {tab === "document" && <DocumentAgentTab />}
        {tab === "race" && <ClaimsRaceTab />}
        {tab === "safety" && <SafetyTab />}
      </TabPanel>
    </>
  );
}

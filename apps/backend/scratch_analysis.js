  import "dotenv/config";
import { db } from "./src/config/db.js";
import { analysisService } from "./src/services/analysis.service.js";
import { jobRepository } from "./src/repositories/job.repository.js";
import { repositoryRepository } from "./src/repositories/repository.repository.js";
import { snapshotRepository } from "./src/repositories/snapshot.repository.js";

async function main() {
  const repos = await db.orm.public.Repository.all();
  console.log("Repositories:");
  for (const r of repos) {
    console.log(`- ${r.id}: ${r.name} (${r.url})`);
  }

  const gymRepo = repos.find(r => r.name.toLowerCase().includes("gym") || r.id === "0b5761ff-3715-4c30-a40a-d11cfc2af204");
  if (!gymRepo) {
    console.log("gym-buddy repo not found");
    return;
  }

  console.log(`Found gym-buddy repo: ${gymRepo.id}`);
  const snapshots = await snapshotRepository.findManyByRepositoryId(gymRepo.id);
  console.log(`Found ${snapshots.length} snapshots:`);
  for (const s of snapshots) {
    console.log(`  Snapshot ${s.id}: commitSha=${s.commitSha}`);
  }

  const targetSha = "8e350490b2688da8742e35d004e75241506b5058";
  let snapshot = snapshots.find(s => s.commitSha === targetSha) || snapshots[0];
  if (!snapshot) {
    console.log("No snapshot found");
    return;
  }
  console.log(`Target snapshot: ${snapshot.id} (${snapshot.commitSha})`);

  // Check existing jobs
  const existingJob = await jobRepository.findBySnapshotId(snapshot.id);
  if (existingJob) {
    console.log(`Existing job: ${existingJob.id}, status=${existingJob.status}`);
    // Delete old job to ensure completely fresh AnalysisJob row and ID
    await db.orm.public.AnalysisJob.where({ id: existingJob.id }).delete();
    console.log(`Deleted old job ${existingJob.id} to ensure fresh analysis.`);
  }

  // Create fresh job
  const newJob = await jobRepository.create(snapshot.id);
  console.log(`Created new AnalysisJob: ${newJob.id}`);

  // Dispatch fresh analysis
  console.log("Dispatching analysis via analysisService.dispatch()...");
  const completedJob = await analysisService.dispatch(newJob, gymRepo, snapshot);
  console.log(`Analysis complete! Job ID: ${completedJob.id}, status: ${completedJob.status}`);

  const result = typeof completedJob.resultJson === "string" ? JSON.parse(completedJob.resultJson) : completedJob.resultJson;
  const graphIr = result.graph;

  console.log("\n--- Analysis Summary ---");
  console.log(`AnalysisJob ID: ${completedJob.id}`);
  console.log(`Snapshot SHA: ${snapshot.commitSha}`);
  console.log(`Graph IR schema_version: ${graphIr.schema_version}`);
  console.log(`Total nodes: ${graphIr.nodes.length}`);
  console.log(`Total edges: ${graphIr.edges.length}`);

  // Check target files
  const targets = [
    "backend/middleware/requireAuth.js",
    "backend/models/usermodel.js",
    "frontend/src/context/useSignupContext.js",
    "frontend/src/hooks/useAuthContext.js",
    "frontend/src/hooks/useLogin.js",
    "frontend/src/hooks/useWorkoutsContext.js",
    "frontend/src/index.js",
    "frontend/src/App.js",
    "frontend/src/index.css",
    "backend/server.js",
    "backend/controllers/userController.js",
    "backend/controllers/workoutController.js",
  ];

  console.log("\n--- File Classifications in Graph IR ---");
  for (const node of graphIr.nodes) {
    if (node.type === "file") {
      const filePath = node.metadata?.path || "";
      for (const t of targets) {
        if (filePath.endsWith(t) || t.endsWith(filePath)) {
          // Find all classified_as edges from this file node
          const classEdges = graphIr.edges.filter(e => e.source === node.id && e.type === "classified_as");
          const roles = classEdges.map(e => e.metadata?.role);
          console.log(`${filePath}: roles=[${roles.join(", ")}]`);
        }
      }
    }
  }

  console.log("\n--- Architecture Edges ---");
  const compToHook = graphIr.edges.filter(e => {
    const srcNode = graphIr.nodes.find(n => n.id === e.source);
    const tgtNode = graphIr.nodes.find(n => n.id === e.target);
    return srcNode?.type === "component" && tgtNode?.type === "hook";
  });
  console.log(`COMPONENT -> HOOK architecture edges count: ${compToHook.length}`);

  console.log("\n--- Controller Function Nodes ---");
  const controllerFuncs = graphIr.nodes.filter(n => (n.type === "function" || n.type === "method") && (n.metadata?.path?.includes("userController") || n.metadata?.path?.includes("workoutController")));
  console.log(`Found ${controllerFuncs.length} controller function/method nodes:`);
  for (const fn of controllerFuncs) {
    console.log(`  ${fn.metadata?.path} :: ${fn.label} (id: ${fn.id})`);
  }
}

main().catch(console.error).finally(() => process.exit(0));

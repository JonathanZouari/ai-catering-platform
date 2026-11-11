// The dish image save sequence. Kept apart from the form so tests can exercise its failure paths.
import { DISH_BUCKET, buildDishImagePath } from "./helpers.js";

// Uploads a new object, then points dishes.image_path at it. Nothing is ever deleted here: a failed
// link response can arrive after the row committed, so the new path may already be the live image.
// Superseded and unlinked objects stay in the bucket until someone cleans them up deliberately.
export async function replaceDishImage({ client, dishId, dishCode, oldPath, file, info, uuid }) {
  const path = buildDishImagePath(dishCode, info.extension, uuid);

  const upload = await client.storage.from(DISH_BUCKET).upload(path, file, { contentType: info.contentType, upsert: false });
  if (upload.error) return { ok: false, stage: "upload", error: upload.error };

  // Matching the previous value stops this save from overwriting a concurrent image change.
  let update = client.from("dishes").update({ image_path: path }).eq("id", dishId);
  update = oldPath ? update.eq("image_path", oldPath) : update.is("image_path", null);
  try {
    const linked = await update.select("id,image_path").single();
    if (linked.error) return { ok: false, stage: "link", error: linked.error };
  } catch (error) {
    return { ok: false, stage: "link", error };
  }
  return { ok: true, path };
}

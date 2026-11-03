import { describe, expect, it } from "vitest";
import { REGIONS as PROFILE_REGIONS } from "@/features/company-profile/data/regions";
import { SEARCH_REGIONS } from "@/features/search/data/searchConstants";
import { toSearchRegion } from "@/features/search/data/profileRegions";
import { REGION_CENTERS, regionCenter } from "../regionCenters";

describe("REGION_CENTERS", () => {
  it("tiene centro para cada región que entiende el backend", () => {
    for (const region of SEARCH_REGIONS) {
      expect(REGION_CENTERS[region], region).toBeDefined();
    }
    expect(Object.keys(REGION_CENTERS)).toHaveLength(SEARCH_REGIONS.length);
  });

  it("toda región del perfil llega a un centro", () => {
    for (const region of PROFILE_REGIONS) {
      const canonica = toSearchRegion(region);
      expect(canonica, region).not.toBeNull();
      expect(regionCenter(canonica ?? "")).not.toBeNull();
    }
  });

  it("los centros caen dentro de Chile continental", () => {
    for (const [region, { lat, lng, zoom }] of Object.entries(REGION_CENTERS)) {
      expect(lat, region).toBeGreaterThan(-56);
      expect(lat, region).toBeLessThan(-17);
      expect(lng, region).toBeGreaterThan(-76);
      expect(lng, region).toBeLessThan(-66);
      expect(zoom, region).toBeGreaterThanOrEqual(5);
    }
  });

  it("una región desconocida no tiene centro", () => {
    expect(regionCenter("Narnia")).toBeNull();
  });
});

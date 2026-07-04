import {
  ActiveScheme,
  BuildFromCatalogPayload,
  BuildingCatalogResponse,
  CityDevelopmentResponse,
  DevApiClient,
  LaunchSchemePayload,
  LaunchSchemeResponse,
  SchemeCatalogResponse,
  api,
} from "@/lib/api";
import { matchApi } from "@/lib/matchApi";

/**
 * Catalogs (buildingCatalog / schemeCatalog) are static reference data —
 * identical for every match — so they're left pointing at the original
 * global endpoints. Only the two *mutating* calls (buildFromCatalog,
 * launchScheme) are rerouted through /api/match/{matchId}/... so they:
 *   - run against that match's isolated city state, and
 *   - have their `role` derived server-side from the caller's seat,
 *     rather than trusting whatever the client sends.
 */
export function createMatchDevClient(matchId: string, token: string): DevApiClient {
  return {
    buildingCatalog: (): Promise<BuildingCatalogResponse> => api.buildingCatalog(),
    schemeCatalog: (): Promise<SchemeCatalogResponse> => api.schemeCatalog(),
    activeSchemes: (): Promise<ActiveScheme[]> => api.activeSchemes(),

    buildFromCatalog: (payload: BuildFromCatalogPayload): Promise<CityDevelopmentResponse> =>
      matchApi.action<CityDevelopmentResponse>(matchId, "development/buildings/build", token, payload),

    launchScheme: (payload: LaunchSchemePayload): Promise<LaunchSchemeResponse> =>
      matchApi.action<LaunchSchemeResponse>(matchId, "development/schemes/launch", token, payload),
  };
}


import os
import arcpy

print("=" * 50)
print("ePUPS Spatial - ArcPy Environment Test")
print("=" * 50)

print(f"ArcGIS Pro version: {arcpy.GetInstallInfo()['Version']}")
print(f"ArcGIS Pro install: {arcpy.GetInstallInfo()['InstallDir']}")
print(f"ArcPy available: {arcpy.ProductInfo()}")

repo = r"\\spatialfiles.bcgov\Work\srm\gss\projects\gr_2026_472_park_use_permits\tools\PUPS"
scripts = os.path.join(repo, "epups-spatial", "scripts")

print(f"Repository accessible: {os.path.exists(repo)}")
print(f"Scripts folder accessible: {os.path.exists(scripts)}")

print("=" * 50)
print("Environment test complete.")

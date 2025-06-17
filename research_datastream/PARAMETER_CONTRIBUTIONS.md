# Research DataStream Community NextGen Parameters
The hydrologic simulations conducted by the Research DataStream are configured with NextGen BMI model parameters. By default, the system will calculate these parameters from the hydrofabric, which means the default parameters are uncalibrated. 

In order to improve the accuracy of the streamflow predictions made by the Research DataStream, these parameters are open to the community and individual members may propose calibrated parameters to be used by the system in future executions. 

If you have calibrated parameters and would like to submit them, you must prepare a data package that abides by the standard below. 

### Submission Standard
A submission data package contains 2 files.

```
├── hydrofabric_subset.gpkg		
├── realization.json				
```


1. The geopackage that holds the hydrofabric used during calibration.
> **_NOTE:_** The hydrofabric is an evolving data product, with new version releases expected semi-annually. Calibrated parameters are only valid for a specific hydrofabric version. As of June 2025, submissions are only accepted with v2.2 hydrofabric.

2. A NextGen realization that holds the parameters and model selection. 

    One of two types of realizations are allowed in the submission.

    1. [Lumped](https://ciroh-community-ngen-datastream.s3.us-east-1.amazonaws.com/realizations/lumped_realization_example.json) - a single set of parameters are defined in the realization. These parameters will be applied to all catchment in the geopackage.
    2. [Per-catchment](https://ciroh-community-ngen-datastream.s3.us-east-1.amazonaws.com/realizations/realization_VPU_16.json) - a set of parameters is defined for each catchment.

Tar up the data package into a single object. Store the object somewhere publicly and provide the object's URL while filling out the submission form [here]() *NEED LINK HERE*.

Example tar command:
```
[jlaser@LYNK-59WW6S3 data]$ tar -czvf example_community_contribution.tar.gz example_community_contribution/
example_community_contribution/
example_community_contribution/gage-10154200_subset.gpkg
example_community_contribution/realization.json
```

Example data package URL:

https://ciroh-community-ngen-datastream.s3.us-east-1.amazonaws.com/submissions/example_community_contribution.tar.gz




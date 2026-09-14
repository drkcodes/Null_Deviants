"""Phase 8 deterministic engine validation. No DB/model/frontend changes."""
from copy import deepcopy
import json
from maintenance_risk import risk_from_health, attach_trajectory_and_horizon, rank_maintenance_results

NOW = "2025-12-30T23:45:00+05:30"

def h(**kw):
    return {
        "timestamp": NOW,
        "overall": {"score": kw.get("score", 95), "status": "Healthy"},
        "drift": {"progressive": kw.get("p",0), "persistence": kw.get("s",0),
                  "run_length": kw.get("r",0), "directional_consistency": kw.get("d",0),
                  "score": 999},
        "sensor_fault": {"frozen": kw.get("f",0), "physical_consistency": kw.get("q",0),
                         "isolation": kw.get("i",0), "score": 999},
        "data_quality": {"missing_rate": kw.get("m",0), "timestamp_gap": kw.get("g",0),
                         "observation_age_seconds": kw.get("age",0)},
        "network": {"coherence": kw.get("c",0), "neighbor_agreement": 0},
        "data_sufficiency": {"status": kw.get("suff","high"), "samples_used": kw.get("n",96)},
    }

def check():
    clean=risk_from_health(h(),[],NOW)
    assert clean["maintenance_risk"]==0 and clean["priority"]=="Monitor"

    drift=risk_from_health(h(p=.9,s=.9,r=5,d=.9,i=.9,c=.1),[],NOW)
    assert drift["maintenance_risk"]>=25
    assert drift["recommended_action"]=="Calibrate / inspect"

    frozen=risk_from_health(h(f=1,i=.9,c=.1),[],NOW)
    assert frozen["groups"]["B_hard_fault"]==1 and frozen["recommended_action"]=="Inspect sensor"
    assert frozen["action_queue"]=="sensor"

    weather_rows=[{"timestamp":NOW,"anomaly":1,"weather_or_sensor":"weather"} for _ in range(8)]
    weather=risk_from_health(h(p=.9,s=.9,r=5,d=.9,i=.1,c=1),weather_rows,NOW)
    assert weather["weather_suppression_applied"] and weather["sensor_anomaly_count_7d"]==0
    assert weather["groups"]["D_sensor_burden_7d"]==0

    comms=risk_from_health(h(m=.9,g=1,age=21600),[],NOW)
    assert comms["action_queue"]=="communications"

    insufficient=risk_from_health(h(suff="insufficient",n=4,score=None),[],NOW)
    assert insufficient["maintenance_risk"] is None and insufficient["confidence"]=="none"

    low=risk_from_health(h(p=1,s=1,r=5,d=1,f=1,i=1,suff="low",n=12),[],NOW)
    assert low["maintenance_risk"]<=49 and low["priority"]!="Priority"

    altered=deepcopy(h(p=.75,s=.7,r=4,d=.8,i=.6))
    base=risk_from_health(altered,[],NOW)
    altered["drift"]["score"]=999999
    altered["sensor_fault"]["score"]=999999
    altered["network"]["neighbor_agreement"]=999999
    altered_result=risk_from_health(altered,[],NOW)
    assert base["maintenance_risk"]==altered_result["maintenance_risk"]
    assert base["groups"]==altered_result["groups"]

    worsening=attach_trajectory_and_horizon(
        drift, {"6h":{"maintenance_risk":35},"24h":{"maintenance_risk":25},"7d":{"maintenance_risk":20}})
    assert worsening["trajectory"]["direction"]=="worsening"

    recovery=deepcopy(drift); recovery["maintenance_risk"]=20
    recovery=attach_trajectory_and_horizon(
        recovery, {"6h":{"maintenance_risk":35},"24h":{"maintenance_risk":40},"7d":{"maintenance_risk":45}})
    assert recovery["trajectory"]["direction"]=="improving"

    ranked=rank_maintenance_results([
        {"station_id":"AWS_AP03","maintenance_risk":60,"confidence":"high","groups":{"B_hard_fault":.2,"D_sensor_burden_7d":.5}},
        {"station_id":"AWS_AP02","maintenance_risk":60,"confidence":"high","groups":{"B_hard_fault":.8,"D_sensor_burden_7d":.1}},
        {"station_id":"AWS_AP01","maintenance_risk":None,"confidence":"none","groups":{"B_hard_fault":0,"D_sensor_burden_7d":0}},
    ])
    assert [x["station_id"] for x in ranked]==["AWS_AP02","AWS_AP03","AWS_AP01"]
    assert ranked[0]["priority_rank"]==1 and ranked[-1]["priority_rank"] is None

    return {
        "clean":clean["maintenance_risk"],
        "drift":drift["maintenance_risk"],
        "frozen":frozen["maintenance_risk"],
        "weather":weather["maintenance_risk"],
        "comms":comms["maintenance_risk"],
        "insufficient":insufficient["maintenance_risk"],
        "low_confidence":low["maintenance_risk"],
        "worsening_delta":worsening["trajectory"]["delta_risk"],
        "recovery_delta":recovery["trajectory"]["delta_risk"],
        "ranking":[x["station_id"] for x in ranked],
    }

if __name__=="__main__":
    result=check()
    print("PHASE 8 ENGINE VALIDATION: PASS")
    print(json.dumps(result,indent=2))

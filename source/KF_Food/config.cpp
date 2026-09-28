class CfgPatches { class KF_Food { units[]={"KF_RamenPacket","KF_RamenCooked","KF_JinHotPacket","KF_JinHotPpogeuli","KF_JinMildPacket","KF_JinMildPpogeuli","KF_AnsungPacket","KF_AnsungPpogeuli","KF_ChapagettiPacket","KF_ChapagettiPpogeuli","KF_CupRamenDry","KF_CupRamenCooked","KF_JinHotCup","KF_JinHotCupReady","KF_JinMildCup","KF_JinMildCupReady","KF_ShrimpCup","KF_ShrimpCupReady","KF_Chopsticks"}; weapons[]={}; requiredVersion=0.1; requiredAddons[]={"DZ_Data","DZ_Gear_Food","DZ_Gear_Cooking","DZ_Gear_Tools","DZ_Gear_Containers","DZ_Characters","DZ_Sounds_Effects"}; }; };
class CfgMods { class KF_Food { dir="KF_Food"; name="Korean Food"; type="mod"; dependencies[]={"World"}; class defs { class worldScriptModule { value=""; files[]={"KF_Food/scripts/4_World"}; }; }; }; };
class CfgVehicles {
 class Man;
 class SurvivorBase: Man {
  class AnimEvents {
   class SoundVoice {
    class takeASip_sip;
    class takeASip_swallow;
    class KF_Slurp: takeASip_sip { id=32101; soundLookupTable="KF_Slurp_LookupTable"; };
    class KF_Swallow: takeASip_swallow { id=32102; soundLookupTable="KF_Swallow_LookupTable"; };
   };
  };
 };

 class Rice; class SpaghettiCan_Opened; class Inventory_Base; class HouseNoDestruct;
 class KF_ChopsticksVisual: HouseNoDestruct { scope=1; model="\KF_Food\models\chopsticks_hand_visual.p3d"; };
 class KF_LiftedNoodlesVisual: HouseNoDestruct { scope=1; model="\KF_Food\models\lifted_noodles_hand.p3d"; };
 class KF_DryNoodles: Rice { scope=0; kfCanEatDry=0; class Nutrition { fullnessIndex=3; energy=90; water=0; nutritionalIndex=1; toxicity=0; }; itemSize[]={2,2}; weight=20; hiddenSelections[]={}; hiddenSelectionsTextures[]={};
  class DamageSystem { class GlobalHealth { class Health { hitpoints=50; healthLevels[]={{1,{}},{0.7,{}},{0.5,{}},{0.3,{}},{0,{}}}; }; }; };
 };
 class KF_PreparedNoodles: SpaghettiCan_Opened { scope=0; itemSize[]={2,3}; weight=20; hiddenSelections[]={}; hiddenSelectionsTextures[]={};
  descriptionShort="$STR_KF_C001";
  class DamageSystem { class GlobalHealth { class Health { hitpoints=50; healthLevels[]={{1,{}},{0.7,{}},{0.5,{}},{0.3,{}},{0,{}}}; }; }; };
  class Nutrition { fullnessIndex=2; energy=95; water=70; nutritionalIndex=1; toxicity=0; };
  class AnimationSources {
   class LidOpen { source="user"; animPeriod=1; initPhase=0; };
   class NoodleLift { source="user"; animPeriod=0.65; initPhase=0; };
   class UtensilsHide { source="user"; animPeriod=0.01; initPhase=1; };
  };
 };
 class KF_RamenPacket: KF_DryNoodles { scope=2; itemSize[]={2,2}; kfCanEatDry=1; displayName="$STR_KF_C002"; descriptionShort="$STR_KF_C003"; model="\KF_Food\models\shin_packet_dry.p3d"; varQuantityInit=120; varQuantityMin=0; varQuantityMax=120; kfWaterMl=500; kfSoakSeconds=60; kfPreparedType="KF_RamenCooked"; };
 class KF_RamenCooked: KF_PreparedNoodles { scope=2; itemSize[]={2,2}; displayName="$STR_KF_C004"; model="\KF_Food\models\shin_packet_ready.p3d"; varQuantityInit=620; varQuantityMin=0; varQuantityMax=620; };
 class KF_JinHotPacket: KF_DryNoodles { scope=2; itemSize[]={2,2}; kfCanEatDry=1; displayName="$STR_KF_C005"; descriptionShort="$STR_KF_C003"; model="\KF_Food\models\jin_hot_packet_dry.p3d"; varQuantityInit=120; varQuantityMin=0; varQuantityMax=120; kfWaterMl=500; kfSoakSeconds=60; kfPreparedType="KF_JinHotPpogeuli"; };
 class KF_JinHotPpogeuli: KF_PreparedNoodles { scope=2; itemSize[]={2,2}; displayName="$STR_KF_C006"; model="\KF_Food\models\jin_hot_packet_ready.p3d"; varQuantityInit=620; varQuantityMin=0; varQuantityMax=620; };
 class KF_JinMildPacket: KF_DryNoodles { scope=2; itemSize[]={2,2}; kfCanEatDry=1; displayName="$STR_KF_C007"; descriptionShort="$STR_KF_C003"; model="\KF_Food\models\jin_mild_packet_dry.p3d"; varQuantityInit=120; varQuantityMin=0; varQuantityMax=120; kfWaterMl=500; kfSoakSeconds=60; kfPreparedType="KF_JinMildPpogeuli"; };
 class KF_JinMildPpogeuli: KF_PreparedNoodles { scope=2; itemSize[]={2,2}; displayName="$STR_KF_C008"; model="\KF_Food\models\jin_mild_packet_ready.p3d"; varQuantityInit=620; varQuantityMin=0; varQuantityMax=620; };
 class KF_AnsungPacket: KF_DryNoodles { scope=2; itemSize[]={2,2}; kfCanEatDry=1; displayName="$STR_KF_C009"; descriptionShort="$STR_KF_C003"; model="\KF_Food\models\ansung_packet_dry.p3d"; varQuantityInit=120; varQuantityMin=0; varQuantityMax=120; kfWaterMl=500; kfSoakSeconds=60; kfPreparedType="KF_AnsungPpogeuli"; };
 class KF_AnsungPpogeuli: KF_PreparedNoodles { scope=2; itemSize[]={2,2}; displayName="$STR_KF_C010"; model="\KF_Food\models\ansung_packet_ready.p3d"; varQuantityInit=620; varQuantityMin=0; varQuantityMax=620; };
 class KF_ChapagettiPacket: KF_DryNoodles { scope=2; itemSize[]={2,2}; kfCanEatDry=1; displayName="$STR_KF_C011"; descriptionShort="$STR_KF_C003"; model="\KF_Food\models\chapagetti_packet_dry.p3d"; varQuantityInit=120; varQuantityMin=0; varQuantityMax=120; kfWaterMl=500; kfSoakSeconds=60; kfPreparedType="KF_ChapagettiPpogeuli"; };
 class KF_ChapagettiPpogeuli: KF_PreparedNoodles { scope=2; itemSize[]={2,2}; displayName="$STR_KF_C012"; model="\KF_Food\models\chapagetti_packet_ready.p3d"; varQuantityInit=620; varQuantityMin=0; varQuantityMax=620; };
 class KF_CupRamenDry: KF_DryNoodles { scope=2; itemSize[]={2,2}; displayName="$STR_KF_C013"; descriptionShort="$STR_KF_C014"; model="\KF_Food\models\shin_cup_dry.p3d"; varQuantityInit=80; varQuantityMin=0; varQuantityMax=80; kfWaterMl=300; kfSoakSeconds=45; kfPreparedType="KF_CupRamenCooked"; };
 class KF_CupRamenCooked: KF_PreparedNoodles { scope=2; itemSize[]={2,2}; displayName="$STR_KF_C015"; model="\KF_Food\models\shin_cup_ready.p3d"; varQuantityInit=380; varQuantityMin=0; varQuantityMax=380; };
 class KF_JinHotCup: KF_DryNoodles { scope=2; itemSize[]={2,2}; displayName="$STR_KF_C016"; descriptionShort="$STR_KF_C014"; model="\KF_Food\models\jin_hot_cup_dry.p3d"; varQuantityInit=80; varQuantityMin=0; varQuantityMax=80; kfWaterMl=300; kfSoakSeconds=45; kfPreparedType="KF_JinHotCupReady"; };
 class KF_JinHotCupReady: KF_PreparedNoodles { scope=2; itemSize[]={2,2}; displayName="$STR_KF_C017"; model="\KF_Food\models\jin_hot_cup_ready.p3d"; varQuantityInit=380; varQuantityMin=0; varQuantityMax=380; };
 class KF_JinMildCup: KF_DryNoodles { scope=2; itemSize[]={2,2}; displayName="$STR_KF_C018"; descriptionShort="$STR_KF_C014"; model="\KF_Food\models\jin_mild_cup_dry.p3d"; varQuantityInit=80; varQuantityMin=0; varQuantityMax=80; kfWaterMl=300; kfSoakSeconds=45; kfPreparedType="KF_JinMildCupReady"; };
 class KF_JinMildCupReady: KF_PreparedNoodles { scope=2; itemSize[]={2,2}; displayName="$STR_KF_C019"; model="\KF_Food\models\jin_mild_cup_ready.p3d"; varQuantityInit=380; varQuantityMin=0; varQuantityMax=380; };
 class KF_ShrimpCup: KF_DryNoodles { scope=2; itemSize[]={2,2}; displayName="$STR_KF_C020"; descriptionShort="$STR_KF_C014"; model="\KF_Food\models\shrimp_cup_dry.p3d"; varQuantityInit=80; varQuantityMin=0; varQuantityMax=80; kfWaterMl=300; kfSoakSeconds=45; kfPreparedType="KF_ShrimpCupReady"; };
 class KF_ShrimpCupReady: KF_PreparedNoodles { scope=2; itemSize[]={2,2}; displayName="$STR_KF_C021"; model="\KF_Food\models\shrimp_cup_ready.p3d"; varQuantityInit=380; varQuantityMin=0; varQuantityMax=380; };
 class KF_Chopsticks: Inventory_Base { scope=2; itemSize[]={1,2}; displayName="$STR_KF_C022"; descriptionShort="$STR_KF_C023"; model="\KF_Food\models\chopsticks.p3d"; weight=8; rotationFlags=17; class DamageSystem { class GlobalHealth { class Health { hitpoints=50; healthLevels[]={{1,{}},{0,{}}}; }; }; }; };
};

class CfgSoundShaders {
 class baseCharacter_SoundShader;
 class KF_NoodleSlurp_None_SoundShader: baseCharacter_SoundShader { samples[]={{"KF_Food\sounds\noodle_slurp.ogg",1}}; volume=1.0; };
 class KF_NoodleSlurp_Metalhelmet_SoundShader: baseCharacter_SoundShader { samples[]={{"KF_Food\sounds\noodle_slurp_metalhelmet.ogg",1}}; volume=0.8; };
 class KF_NoodleSlurp_Gasmask_SoundShader: baseCharacter_SoundShader { samples[]={{"KF_Food\sounds\noodle_slurp_gasmask.ogg",1}}; volume=0.7; };
 class KF_NoodleSlurp_Motohelmet_SoundShader: baseCharacter_SoundShader { samples[]={{"KF_Food\sounds\noodle_slurp_motohelmet.ogg",1}}; volume=0.75; };
 class KF_NoodleSlurp_Gag_SoundShader: baseCharacter_SoundShader { samples[]={{"KF_Food\sounds\noodle_slurp_gag.ogg",1}}; volume=0.55; };
};
class CfgSoundSets {
 class takeASip_sip_SoundVoice_Char_SoundSet;
 class KF_Slurp_None_SoundSet: takeASip_sip_SoundVoice_Char_SoundSet { soundShaders[]={"KF_NoodleSlurp_None_SoundShader"}; volumeFactor=1.0; };
 class greathelmet_takeASip_sip_SoundVoice_Char_SoundSet;
 class KF_Slurp_Metalhelmet_SoundSet: greathelmet_takeASip_sip_SoundVoice_Char_SoundSet { soundShaders[]={"KF_NoodleSlurp_Metalhelmet_SoundShader"}; volumeFactor=1.0; };
 class gasmask_takeASip_sip_SoundVoice_Char_SoundSet;
 class KF_Slurp_Gasmask_SoundSet: gasmask_takeASip_sip_SoundVoice_Char_SoundSet { soundShaders[]={"KF_NoodleSlurp_Gasmask_SoundShader"}; volumeFactor=1.0; };
 class motohelmet_takeASip_sip_SoundVoice_Char_SoundSet;
 class KF_Slurp_Motohelmet_SoundSet: motohelmet_takeASip_sip_SoundVoice_Char_SoundSet { soundShaders[]={"KF_NoodleSlurp_Motohelmet_SoundShader"}; volumeFactor=1.0; };
 class gag_takeASip_sip_SoundVoice_Char_SoundSet;
 class KF_Slurp_Gag_SoundSet: gag_takeASip_sip_SoundVoice_Char_SoundSet { soundShaders[]={"KF_NoodleSlurp_Gag_SoundShader"}; volumeFactor=1.0; };
 class takeASip_swallow_SoundVoice_Char_SoundSet;
 class KF_Swallow_None_SoundSet: takeASip_swallow_SoundVoice_Char_SoundSet { volumeFactor=1.35; };
 class greathelmet_takeASip_swallow_SoundVoice_Char_SoundSet;
 class KF_Swallow_Metalhelmet_SoundSet: greathelmet_takeASip_swallow_SoundVoice_Char_SoundSet { volumeFactor=1.35; };
 class gasmask_takeASip_swallow_SoundVoice_Char_SoundSet;
 class KF_Swallow_Gasmask_SoundSet: gasmask_takeASip_swallow_SoundVoice_Char_SoundSet { volumeFactor=1.35; };
 class motohelmet_takeASip_swallow_SoundVoice_Char_SoundSet;
 class KF_Swallow_Motohelmet_SoundSet: motohelmet_takeASip_swallow_SoundVoice_Char_SoundSet { volumeFactor=1.35; };
 class gag_takeASip_swallow_SoundVoice_Char_SoundSet;
 class KF_Swallow_Gag_SoundSet: gag_takeASip_swallow_SoundVoice_Char_SoundSet { volumeFactor=1.35; };
};
class CfgSoundTables {
 class CfgVoiceSoundTables {
  class KF_Slurp_LookupTable {
   class None { category="none"; soundSets[]={"KF_Slurp_None_SoundSet"}; };
   class Metalhelmet { category="metalhelmet"; soundSets[]={"KF_Slurp_Metalhelmet_SoundSet"}; };
   class Gasmask { category="gasmask"; soundSets[]={"KF_Slurp_Gasmask_SoundSet"}; };
   class Motohelmet { category="motohelmet"; soundSets[]={"KF_Slurp_Motohelmet_SoundSet"}; };
   class Gag { category="gag"; soundSets[]={"KF_Slurp_Gag_SoundSet"}; };
  };
  class KF_Swallow_LookupTable {
   class None { category="none"; soundSets[]={"KF_Swallow_None_SoundSet"}; };
   class Metalhelmet { category="metalhelmet"; soundSets[]={"KF_Swallow_Metalhelmet_SoundSet"}; };
   class Gasmask { category="gasmask"; soundSets[]={"KF_Swallow_Gasmask_SoundSet"}; };
   class Motohelmet { category="motohelmet"; soundSets[]={"KF_Swallow_Motohelmet_SoundSet"}; };
   class Gag { category="gag"; soundSets[]={"KF_Swallow_Gag_SoundSet"}; };
  };
 };
};

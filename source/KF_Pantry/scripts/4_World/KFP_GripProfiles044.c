// Use a container grip for both states of the combat-ration box.
// Inventory_Base otherwise falls back to the apple hand pose.
modded class ModItemRegisterCallbacks
{
    override void RegisterOneHanded(DayZPlayerType pType, DayzPlayerItemBehaviorCfg pBehavior)
    {
        super.RegisterOneHanded(pType, pBehavior);
        pType.AddItemInHandsProfileIK("KFR_Sealed", "dz/anims/workspaces/player/player_main/player_main_1h.asi", pBehavior, "dz/anims/anm/player/ik/gear/protector_case.anm");
        pType.AddItemInHandsProfileIK("KFR_OpenBox", "dz/anims/workspaces/player/player_main/player_main_1h.asi", pBehavior, "dz/anims/anm/player/ik/gear/protector_case.anm");
    }
};

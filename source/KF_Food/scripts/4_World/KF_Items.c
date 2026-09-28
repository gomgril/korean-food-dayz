class KF_ItemActions
{
    // Action registration also runs on a dedicated server without a local player.
    static void Remove(ItemBase item, typename actionType)
    {
        ActionBase action = ActionManagerBase.GetAction(actionType);
        if (!action || !item.m_InputActionMap) return;
        array<ActionBase_Basic> actions = item.m_InputActionMap.Get(action.GetInputType());
        if (actions) actions.RemoveItem(action);
    }
};
class KF_DryNoodles: Rice
{
    protected bool m_KF_Used;
    bool KF_IsUsed() { return m_KF_Used; }
    void KF_MarkUsed() { m_KF_Used = true; }
    override bool CanBeConsumed(ConsumeConditionData data = null)
    {
        return !m_KF_Used && ConfigGetBool("kfCanEatDry") && super.CanBeConsumed(data);
    }
    override void SetActions()
    {
        super.SetActions();
        KF_ItemActions.Remove(this, ActionEatBig);
        KF_ItemActions.Remove(this, ActionForceFeed);
        if (ConfigGetBool("kfCanEatDry")) AddAction(KF_ActionEatDryNoodles);
        AddAction(KF_ActionTakeHotWater);
    }
};
class KF_RamenPacket: KF_DryNoodles {};
class KF_JinHotPacket: KF_DryNoodles {};
class KF_JinMildPacket: KF_DryNoodles {};
class KF_AnsungPacket: KF_DryNoodles {};
class KF_ChapagettiPacket: KF_DryNoodles {};
class KF_CupRamenDry: KF_DryNoodles {};
class KF_JinHotCup: KF_DryNoodles {};
class KF_JinMildCup: KF_DryNoodles {};
class KF_ShrimpCup: KF_DryNoodles {};
class KF_Chopsticks: Inventory_Base {};

class KF_PreparedNoodles: SpaghettiCan_Opened
{
    protected int m_KF_SecondsLeft;
    protected bool m_KF_Eating;
    protected ref Timer m_KF_SoakTimer;
    protected ref Timer m_KF_VisualTimer;
    protected Object m_KF_ChopstickVisual;
    protected Object m_KF_NoodleVisual;
    protected PlayerBase m_KF_VisualOwner;
    protected vector m_KF_GripLocal[4];
    protected int m_KF_NoodleLoopCounter;
    protected int m_KF_ObservedNoodleLoopCounter;
    protected int m_KF_NoodleLoopAt = -1;
    void KF_PreparedNoodles()
    {
        RegisterNetSyncVariableInt("m_KF_SecondsLeft", 0, 600);
        RegisterNetSyncVariableBool("m_KF_Eating");
        RegisterNetSyncVariableInt("m_KF_NoodleLoopCounter",0,255);
    }
    void ~KF_PreparedNoodles()
    {
        if (m_KF_SoakTimer) m_KF_SoakTimer.Stop();
        if (m_KF_VisualTimer) m_KF_VisualTimer.Stop();
        KF_RemoveChopstickVisual();
    }
    bool KF_IsReady() { return m_KF_SecondsLeft == 0; }
    override bool NameOverride(out string output)
    {
        output = KF_Lang.ConfigText(this, "displayName");
        if (KF_IsReady()) output += KF_Lang.Text("STR_KF_S_READY");
        else output += KF_Lang.Text("STR_KF_S_SOAKING");
        return true;
    }
    void KF_BeginSoaking(int seconds)
    {
        if (!GetGame().IsServer()) return;
        m_KF_SecondsLeft = seconds;
        KF_StartTimer();
        SetSynchDirty();
        KF_UpdateVisual();
    }
    void KF_StartTimer()
    {
        if (!GetGame().IsServer() || m_KF_SecondsLeft <= 0) return;
        if (!m_KF_SoakTimer) m_KF_SoakTimer = new Timer(CALL_CATEGORY_SYSTEM);
        if (!m_KF_SoakTimer.IsRunning()) m_KF_SoakTimer.Run(1, this, "KF_SoakTick", null, true);
    }
    void KF_SoakTick()
    {
        m_KF_SecondsLeft = Math.Max(0, m_KF_SecondsLeft - 1);
        if (m_KF_SecondsLeft == 0)
        {
            m_KF_SoakTimer.Stop();
            SetSynchDirty();
            KF_UpdateVisual();
        }
    }
    void KF_SetEating(bool state)
    {
        m_KF_Eating = state;
        if (!state) m_KF_NoodleLoopAt = -1;
        if (GetGame().IsServer()) SetSynchDirty();
        KF_UpdateVisual();
    }
    void KF_StartNoodleLoop()
    {
        m_KF_NoodleLoopAt = GetGame().GetTime();
        if (GetGame().IsServer())
        {
            m_KF_NoodleLoopCounter++;
            if (m_KF_NoodleLoopCounter > 255) m_KF_NoodleLoopCounter = 1;
            SetSynchDirty();
        }
    }
    float KF_NoodleAmount(float elapsedSeconds)
    {
        if (elapsedSeconds < 0.5 || elapsedSeconds >= 2.6) return 0;
        if (elapsedSeconds < 1.4) return Math.Clamp((elapsedSeconds - 0.5) / 0.9,0,1);
        return Math.Clamp(1 - (elapsedSeconds - 1.4) / 1.2,0,1);
    }
    void KF_UpdateVisual()
    {
        if (GetGame().IsDedicatedServer()) return;
        if (KF_IsReady()) SetAnimationPhase("LidOpen", 1);
        else SetAnimationPhase("LidOpen", 0);
        // The old model utensils are cup-relative and must never be shown.
        SetAnimationPhase("UtensilsHide", 1);
        SetAnimationPhase("NoodleLift", 0);
        if (m_KF_Eating)
        {
            if (!m_KF_VisualTimer) m_KF_VisualTimer = new Timer(CALL_CATEGORY_SYSTEM);
            if (!m_KF_VisualTimer.IsRunning()) m_KF_VisualTimer.Run(0.033, this, "KF_UpdateChopstickVisual", null, true);
            KF_UpdateChopstickVisual();
        }
        else
        {
            if (m_KF_VisualTimer) m_KF_VisualTimer.Stop();
            KF_RemoveChopstickVisual();
        }
    }
    void KF_RemoveChopstickVisual()
    {
        KF_RemoveNoodleVisual();
        if (m_KF_ChopstickVisual)
        {
            if (m_KF_VisualOwner) m_KF_VisualOwner.RemoveChild(m_KF_ChopstickVisual);
            if (GetGame()) GetGame().ObjectDelete(m_KF_ChopstickVisual);
        }
        m_KF_ChopstickVisual = null;
        m_KF_VisualOwner = null;
    }
    void KF_RemoveNoodleVisual()
    {
        if (!m_KF_NoodleVisual) return;
        if (m_KF_VisualOwner) m_KF_VisualOwner.RemoveChild(m_KF_NoodleVisual);
        if (GetGame()) GetGame().ObjectDelete(m_KF_NoodleVisual);
        m_KF_NoodleVisual = null;
    }
    void KF_UpdateNoodleVisual()
    {
        if (!m_KF_VisualOwner || m_KF_NoodleLoopAt < 0) { KF_RemoveNoodleVisual(); return; }
        float elapsed = (GetGame().GetTime() - m_KF_NoodleLoopAt) * 0.001;
        float amount = KF_NoodleAmount(elapsed);
        if (amount < 0.03) { KF_RemoveNoodleVisual(); return; }
        if (!m_KF_NoodleVisual)
        {
            m_KF_NoodleVisual = GetGame().CreateObjectEx("KF_LiftedNoodlesVisual","0 0 0",ECE_LOCAL | ECE_NOLIFETIME);
            if (!m_KF_NoodleVisual) return;
            int bone = m_KF_VisualOwner.GetBoneIndexByName("RightHand");
            if (bone < 0 || !m_KF_VisualOwner.AddChild(m_KF_NoodleVisual,bone)) { KF_RemoveNoodleVisual(); return; }
        }
        vector tip = m_KF_NoodleVisual.GetMemoryPointPos("kf_noodle_tip");
        vector origin = m_KF_NoodleVisual.GetMemoryPointPos("kf_grip_origin");
        vector localMatrix[4];
        for (int axis = 0; axis < 3; axis++) localMatrix[axis] = m_KF_GripLocal[axis] * amount;
        vector anchor = tip * (1 - amount) - origin;
        localMatrix[3] = m_KF_GripLocal[3] + m_KF_GripLocal[0] * anchor[0] + m_KF_GripLocal[1] * anchor[1] + m_KF_GripLocal[2] * anchor[2];
        m_KF_NoodleVisual.SetTransform(localMatrix);
    }
    void KF_UpdateChopstickVisual()
    {
        PlayerBase owner = PlayerBase.Cast(GetHierarchyRootPlayer());
        if (!m_KF_Eating || !owner || !owner.IsAlive() || owner.IsUnconscious() || owner.GetItemInHands() != this)
        {
            KF_RemoveChopstickVisual();
            return;
        }
        if (m_KF_ChopstickVisual && m_KF_VisualOwner == owner) { KF_UpdateNoodleVisual(); return; }
        KF_RemoveChopstickVisual();
        int bone = owner.GetBoneIndexByName("RightHand");
        int indexBone = owner.GetBoneIndexByName("RightHandIndex1");
        int middleBone = owner.GetBoneIndexByName("RightHandMiddle1");
        if (bone < 0 || indexBone < 0 || middleBone < 0) return;
        // Locate the grip from knuckle positions. This avoids assuming that
        // the game model uses the Blender hand bone's local rotation axes.
        vector handMatrix[4]; vector indexMatrix[4]; vector middleMatrix[4];
        owner.GetBoneTransformMS(bone, handMatrix);
        owner.GetBoneTransformMS(indexBone, indexMatrix);
        owner.GetBoneTransformMS(middleBone, middleMatrix);
        vector gripX = indexMatrix[3] - handMatrix[3];
        vector knuckleLine = middleMatrix[3] - indexMatrix[3];
        vector gripZ = gripX * knuckleLine;
        if (gripX.LengthSq() < 0.000001 || gripZ.LengthSq() < 0.00000001) return;
        gripX.Normalize();
        gripZ.Normalize();
        vector gripMatrix[4]; vector gripLocal[4];
        gripMatrix[0] = gripX;
        gripMatrix[1] = gripZ * gripX;
        gripMatrix[2] = gripZ;
        gripMatrix[3] = indexMatrix[3];
        Math3D.MatrixInvMultiply4(handMatrix, gripMatrix, gripLocal);
        for (int axis = 0; axis < 4; axis++) m_KF_GripLocal[axis] = gripLocal[axis];
        Object visual = GetGame().CreateObjectEx("KF_ChopsticksVisual", "0 0 0", ECE_LOCAL | ECE_NOLIFETIME);
        if (!visual) return;
        // The visual-only P3D is auto-centred by the engine. Its memory anchor
        // moves with the mesh; compensate that measured shift before parenting.
        vector modelAnchor = visual.GetMemoryPointPos("kf_grip_origin");
        vector anchorOffset = gripLocal[0] * modelAnchor[0] + gripLocal[1] * modelAnchor[1] + gripLocal[2] * modelAnchor[2];
        gripLocal[3] = gripLocal[3] - anchorOffset;
        visual.SetTransform(gripLocal);
        if (!owner.AddChild(visual, bone))
        {
            GetGame().ObjectDelete(visual);
            return;
        }
        m_KF_ChopstickVisual = visual;
        m_KF_VisualOwner = owner;
        KF_UpdateNoodleVisual();
    }
    override void EEDelete(EntityAI parent)
    {
        if (m_KF_VisualTimer) m_KF_VisualTimer.Stop();
        KF_RemoveChopstickVisual();
        super.EEDelete(parent);
    }
    override void EEItemLocationChanged(notnull InventoryLocation oldLoc, notnull InventoryLocation newLoc)
    {
        super.EEItemLocationChanged(oldLoc, newLoc);
        if (!GetGame().IsDedicatedServer()) KF_UpdateChopstickVisual();
    }
    override void EEInit() { super.EEInit(); KF_UpdateVisual(); }
    override void OnVariablesSynchronized()
    {
        super.OnVariablesSynchronized();
        if (m_KF_ObservedNoodleLoopCounter != m_KF_NoodleLoopCounter)
        {
            m_KF_ObservedNoodleLoopCounter = m_KF_NoodleLoopCounter;
            if (m_KF_Eating) m_KF_NoodleLoopAt = GetGame().GetTime();
        }
        KF_UpdateVisual();
    }
    override void OnStoreSave(ParamsWriteContext ctx) { super.OnStoreSave(ctx); ctx.Write(m_KF_SecondsLeft); }
    override bool OnStoreLoad(ParamsReadContext ctx, int version)
    {
        if (!super.OnStoreLoad(ctx, version)) return false;
        // v0.1 had no custom field. Existing cooked servings remain edible.
        if (!ctx.Read(m_KF_SecondsLeft)) m_KF_SecondsLeft = 0;
        m_KF_SecondsLeft = Math.Clamp(m_KF_SecondsLeft, 0, 600);
        return true;
    }
    override void AfterStoreLoad() { super.AfterStoreLoad(); KF_StartTimer(); KF_UpdateVisual(); }
    override bool CanBeConsumed(ConsumeConditionData data = null) { return KF_IsReady() && super.CanBeConsumed(data); }
    override void SetActions()
    {
        super.SetActions();
        KF_ItemActions.Remove(this, ActionEatCan);
        KF_ItemActions.Remove(this, ActionForceFeedCan);
        AddAction(KF_ActionEatNoodles);
    }
};
class KF_RamenCooked: KF_PreparedNoodles {};
class KF_JinHotPpogeuli: KF_PreparedNoodles {};
class KF_JinMildPpogeuli: KF_PreparedNoodles {};
class KF_AnsungPpogeuli: KF_PreparedNoodles {};
class KF_ChapagettiPpogeuli: KF_PreparedNoodles {};
class KF_CupRamenCooked: KF_PreparedNoodles {};
class KF_JinHotCupReady: KF_PreparedNoodles {};
class KF_JinMildCupReady: KF_PreparedNoodles {};
class KF_ShrimpCupReady: KF_PreparedNoodles {};

modded class ModItemRegisterCallbacks
{
    override void RegisterOneHanded(DayZPlayerType pType, DayzPlayerItemBehaviorCfg pBehavior)
    {
        super.RegisterOneHanded(pType, pBehavior);
        // Native box-food animation includes the crunchy SoundVoice event (890).
        pType.AddItemInHandsProfileIK("KF_RamenPacket", "dz/anims/workspaces/player/player_main/props/player_main_1h_food_box.asi", pBehavior, "dz/anims/anm/player/ik/gear/rice.anm");
        pType.AddItemInHandsProfileIK("KF_JinHotPacket", "dz/anims/workspaces/player/player_main/props/player_main_1h_food_box.asi", pBehavior, "dz/anims/anm/player/ik/gear/rice.anm");
        pType.AddItemInHandsProfileIK("KF_JinMildPacket", "dz/anims/workspaces/player/player_main/props/player_main_1h_food_box.asi", pBehavior, "dz/anims/anm/player/ik/gear/rice.anm");
        pType.AddItemInHandsProfileIK("KF_AnsungPacket", "dz/anims/workspaces/player/player_main/props/player_main_1h_food_box.asi", pBehavior, "dz/anims/anm/player/ik/gear/rice.anm");
        pType.AddItemInHandsProfileIK("KF_ChapagettiPacket", "dz/anims/workspaces/player/player_main/props/player_main_1h_food_box.asi", pBehavior, "dz/anims/anm/player/ik/gear/rice.anm");
        pType.AddItemInHandsProfileIK("KF_PreparedNoodles", "KF_Food/animations/kf_food.asi", pBehavior, "dz/anims/anm/player/ik/gear/food_can_opened.anm");
        pType.AddItemInHandsProfileIK("KF_RamenCooked", "KF_Food/animations/kf_food.asi", pBehavior, "dz/anims/anm/player/ik/gear/food_can_opened.anm");
        pType.AddItemInHandsProfileIK("KF_JinHotPpogeuli", "KF_Food/animations/kf_food.asi", pBehavior, "dz/anims/anm/player/ik/gear/food_can_opened.anm");
        pType.AddItemInHandsProfileIK("KF_JinMildPpogeuli", "KF_Food/animations/kf_food.asi", pBehavior, "dz/anims/anm/player/ik/gear/food_can_opened.anm");
        pType.AddItemInHandsProfileIK("KF_AnsungPpogeuli", "KF_Food/animations/kf_food.asi", pBehavior, "dz/anims/anm/player/ik/gear/food_can_opened.anm");
        pType.AddItemInHandsProfileIK("KF_ChapagettiPpogeuli", "KF_Food/animations/kf_food.asi", pBehavior, "dz/anims/anm/player/ik/gear/food_can_opened.anm");
        pType.AddItemInHandsProfileIK("KF_CupRamenCooked", "KF_Food/animations/kf_food.asi", pBehavior, "dz/anims/anm/player/ik/gear/food_can_opened.anm");
        pType.AddItemInHandsProfileIK("KF_JinHotCupReady", "KF_Food/animations/kf_food.asi", pBehavior, "dz/anims/anm/player/ik/gear/food_can_opened.anm");
        pType.AddItemInHandsProfileIK("KF_JinMildCupReady", "KF_Food/animations/kf_food.asi", pBehavior, "dz/anims/anm/player/ik/gear/food_can_opened.anm");
        pType.AddItemInHandsProfileIK("KF_ShrimpCupReady", "KF_Food/animations/kf_food.asi", pBehavior, "dz/anims/anm/player/ik/gear/food_can_opened.anm");
        pType.AddItemInHandsProfileIK("KF_Chopsticks", "dz/anims/workspaces/player/player_main/player_main_1h.asi", pBehavior, "dz/anims/anm/player/ik/gear/WoodenStick.anm");
        pType.AddItemInHandsProfileIK("KF_CupRamenDry", "dz/anims/workspaces/player/player_main/player_main_1h.asi", pBehavior, "dz/anims/anm/player/ik/gear/food_can_opened.anm");
        pType.AddItemInHandsProfileIK("KF_JinHotCup", "dz/anims/workspaces/player/player_main/player_main_1h.asi", pBehavior, "dz/anims/anm/player/ik/gear/food_can_opened.anm");
        pType.AddItemInHandsProfileIK("KF_JinMildCup", "dz/anims/workspaces/player/player_main/player_main_1h.asi", pBehavior, "dz/anims/anm/player/ik/gear/food_can_opened.anm");
        pType.AddItemInHandsProfileIK("KF_ShrimpCup", "dz/anims/workspaces/player/player_main/player_main_1h.asi", pBehavior, "dz/anims/anm/player/ik/gear/food_can_opened.anm");
    }
};
